#!/usr/bin/env python3
"""Dated Danish registry evidence and reproducible blocklist analysis.

Standard-library only. This extension never changes the original observations,
raw blocklist files, reports, menu or comparisons. See DANISH_ANALYSIS_README.md.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import html
import ipaddress
import itertools
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

VERSION = "1.0.0"
ROOT = Path(__file__).resolve().parents[1]
API = "https://stat.ripe.net/data/country-resource-list/data.json"
DEFAULT_SOURCES = ["FireHOL", "Spamhaus DROP", "blocklist.de"]
ALIASES = {"firehol": "FireHOL", "spamhaus": "Spamhaus DROP",
           "spamhaus drop": "Spamhaus DROP", "blocklist_de": "blocklist.de"}
REQUIRED = {"snapshot_id", "source_name", "retrieved_at_utc", "source_path",
            "sha256", "indicator_type", "indicator"}
NA = "NA"


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]


def sha(path):
    with Path(path).open("rb") as f:
        digest = hashlib.sha256()
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def csv_read(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


def csv_write(path, rows, fields=None):
    rows = list(rows)
    fields = fields or (list(rows[0]) if rows else ["status"])
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def timestamp(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Collection timestamp lacks a timezone")
    return dt.astimezone(timezone.utc)


def calendar(start, end):
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    if b < a or (b - a).days > 3660:
        raise ValueError("Invalid study window (maximum 3660 days)")
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


def issue(issues, severity, code, detail, day="", source=""):
    issues.append(dict(severity=severity, code=code, date=day, source=source, detail=str(detail)))


@lru_cache(maxsize=150000)
def network(key):
    kind, value = key
    if kind == "ip":
        addr = ipaddress.ip_address(value)
        return ipaddress.ip_network(f"{addr}/{addr.max_prefixlen}")
    if kind == "cidr":
        return ipaddress.ip_network(value, strict=True)
    raise ValueError("Not an IP indicator")


def merge(parts):
    result = []
    for a, b in sorted(parts):
        if result and a <= result[-1][1] + 1:
            result[-1] = (result[-1][0], max(result[-1][1], b))
        else:
            result.append((a, b))
    return result


def intersection(left, right):
    result, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        a, b = left[i]; c, d = right[j]
        if max(a, c) <= min(b, d):
            result.append((max(a, c), min(b, d)))
        if b < d:
            i += 1
        else:
            j += 1
    return result


def size(parts):
    return sum(b - a + 1 for a, b in parts)


def cidrs(parts, version):
    address = ipaddress.IPv4Address if version == 4 else ipaddress.IPv6Address
    return ";".join(str(n) for a, b in parts for n in
                    ipaddress.summarize_address_range(address(a), address(b)))


class Ranges:
    """Sorted, merged address intervals; CIDRs are never expanded into IPs."""
    def __init__(self, prefixes):
        values = {4: [], 6: []}
        for value in prefixes:
            n = ipaddress.ip_network(value, strict=True)
            values[n.version].append((int(n.network_address), int(n.broadcast_address)))
        self.parts = {v: merge(p) for v, p in values.items()}
        self.ends = {v: [b for _, b in p] for v, p in self.parts.items()}

    def match(self, key):
        n = network(key)
        a, b = int(n.network_address), int(n.broadcast_address)
        values = self.parts[n.version]
        i = bisect.bisect_left(self.ends[n.version], a)
        hits = []
        while i < len(values) and values[i][0] <= b:
            hits.append((max(a, values[i][0]), min(b, values[i][1])))
            i += 1
        count = size(hits)
        label = "DK_FULL" if count == n.num_addresses else "DK_PARTIAL" if count else "NO_DK_MATCH"
        return label, n.version, hits


@dataclass
class Snapshot:
    source: str
    day: str
    id: str
    dt: datetime
    path: str
    digest: str
    keys: set = field(default_factory=set)
    rows: int = 0
    invalid: int = 0
    conflicts: int = 0
    blocked: str = ""
    raw_status: str = "not_checked"


def local_raw(root, value):
    value = value.replace("\\", "/")
    marker = "data/raw/"
    if marker not in value:
        return None
    path = (root / marker / value.split(marker, 1)[1]).resolve()
    return path if path.is_relative_to((root / "data/raw").resolve()) else None


def load_snapshots(root, input_path, issues):
    groups = {}
    with input_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError("Missing observations columns: " + ", ".join(sorted(missing)))
        for line, row in enumerate(reader, 2):
            try:
                dt = timestamp(row["retrieved_at_utc"])
                source = row["source_name"].strip()
                sid = row["snapshot_id"].strip()
                if not source or not sid:
                    raise ValueError("Empty source or snapshot ID")
            except (ValueError, TypeError, KeyError) as e:
                # A row without reliable provenance cannot be silently discarded.
                raise ValueError(f"Input line {line}: {e}") from e
            day = dt.date().isoformat()
            ident = (source, day, sid)
            if ident not in groups:
                groups[ident] = Snapshot(source, day, sid, dt, row["source_path"], row["sha256"])
            snap = groups[ident]
            snap.rows += 1
            if (snap.dt, snap.path, snap.digest) != (dt, row["source_path"], row["sha256"]):
                snap.conflicts += 1
            try:
                kind, value = row["indicator_type"].strip().lower(), row["indicator"].strip()
                if not value or kind not in {"ip", "cidr", "domain", "url"}:
                    raise ValueError("Empty or unsupported indicator")
                key = (kind, value)
                if kind in {"ip", "cidr"}:
                    n = network(key)
                    key = (kind, str(n.network_address) if kind == "ip" else str(n))
                if row.get("status", "listed") not in {"", "listed"}:
                    raise ValueError("Unexpected normalized status")
                snap.keys.add(key)
            except (ValueError, TypeError):
                snap.invalid += 1
    if not groups:
        raise ValueError("No normalized observations found")
    candidates = defaultdict(list)
    for snap in groups.values():
        candidates[(snap.source, snap.day)].append(snap)
    selected = {}
    for pair, versions in candidates.items():
        snap = max(versions, key=lambda s: (s.dt, s.id))
        selected[pair] = snap
        if sum(s.dt == snap.dt for s in versions) > 1:
            snap.blocked = "ambiguous_latest_timestamp"
        if snap.invalid or snap.conflicts:
            snap.blocked = "invalid_or_conflicting_rows"
        if snap.day > datetime.now(timezone.utc).date().isoformat():
            snap.blocked = "future_observation_date"
        if snap.blocked:
            issue(issues, "ERROR", snap.blocked, f"Snapshot {snap.id}; invalid={snap.invalid}; conflicts={snap.conflicts}", snap.day, snap.source)
        path = local_raw(root, snap.path)
        if path and path.is_file():
            if sha(path) == snap.digest:
                snap.raw_status = "hash_verified"
            else:
                snap.raw_status = "hash_mismatch"
                snap.blocked = "raw_hash_mismatch"
                issue(issues, "ERROR", snap.blocked, str(path), snap.day, snap.source)
        else:
            snap.raw_status = "raw_file_not_found"
            issue(issues, "WARN", snap.raw_status, snap.path, snap.day, snap.source)
    collection_path = root / "logs/collection_log.csv"
    if collection_path.exists():
        for row in csv_read(collection_path):
            source = ALIASES.get(row.get("source", "").lower(), row.get("source", ""))
            try:
                dt = timestamp(row["retrieved_at_utc"])
            except (ValueError, KeyError, TypeError):
                issue(issues, "WARN", "invalid_collection_log_time", row)
                continue
            day = dt.date().isoformat()
            pair = (source, day)
            success = row.get("status", "").lower() == "ok" and row.get("http_status") == "200"
            if success:
                represented = any(s.dt == dt and s.digest == row.get("sha256") for s in candidates.get(pair, []))
                if not represented:
                    issue(issues, "WARN", "download_not_in_normalized_input",
                          "Downloaded file has no matching normalized snapshot; empty/invalid/unprocessed is unknown: " + row.get("path", ""), day, source)
                    # Do not silently fall back to an earlier successful snapshot.
                    if pair in selected and dt >= selected[pair].dt:
                        selected[pair].blocked = "newer_download_not_normalized"
                        issue(issues, "ERROR", "source_day_blocked", "Newer successful download is absent from normalized input; normalize and rerun", day, source)
            else:
                issue(issues, "WARN", "collection_attempt_not_successful", row.get("notes", "") or row.get("status", ""), day, source)
    else:
        issue(issues, "WARN", "collection_log_missing", str(collection_path))
    index = []
    for snap in sorted(groups.values(), key=lambda s: (s.day, s.source, s.dt, s.id)):
        index.append(dict(date=snap.day, source=snap.source, snapshot_id=snap.id,
                          timestamp_utc=snap.dt.isoformat(), selected=selected[(snap.source, snap.day)] is snap,
                          input_rows=snap.rows, unique_indicators=len(snap.keys), duplicate_rows=snap.rows-len(snap.keys)-snap.invalid,
                          invalid_rows=snap.invalid, blocked=snap.blocked, raw_status=snap.raw_status,
                          source_path=snap.path, sha256=snap.digest))
    return selected, index


def validate_evidence(payload, day):
    if payload.get("status") != "ok":
        raise ValueError("RIPEstat response is not successful")
    data = payload["data"]
    if data.get("query_time", "")[:10] != day:
        raise ValueError("Evidence query date differs from observation date")
    if data.get("resource", "DK").upper() != "DK":
        raise ValueError("Evidence country is not DK")
    resources = data["resources"]
    if not all(isinstance(resources.get(k), list) and resources[k] for k in ("ipv4", "ipv6")):
        raise ValueError("DK evidence requires non-empty IPv4 and IPv6 lists")
    ranges = Ranges(resources["ipv4"] + resources["ipv6"])
    return ranges


def evidence_for_day(root, day, fetch, issues):
    directory = root / "data/danish_registry_evidence" / day
    existing = sorted(directory.glob("*.metadata.json"))
    if existing:
        meta_path = existing[-1]
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            raw = directory / Path(meta["response_file"]).name
            if meta["requested_date"] != day or meta["country"] != "DK" or meta["sha256"] != sha(raw):
                raise ValueError("Cached evidence identity or checksum mismatch")
            ranges = validate_evidence(json.loads(raw.read_text(encoding="utf-8")), day)
            meta["metadata_path"] = str(meta_path)
            meta["response_path"] = str(raw)
            return ranges, meta
        except (OSError, ValueError, KeyError, TypeError) as e:
            issue(issues, "WARN", "invalid_evidence_cache", e, day)
    if not fetch:
        issue(issues, "WARN", "dated_DK_evidence_missing", "Run with --fetch to request historical DK registry evidence", day)
        return None, None
    if date.fromisoformat(day) > datetime.now(timezone.utc).date():
        issue(issues, "ERROR", "future_evidence_request_rejected", day, day)
        return None, None
    url = API + "?" + urllib.parse.urlencode({"resource": "dk", "time": day, "v4_format": "prefix"})
    agent = os.environ.get("BLOCKLIST_USER_AGENT", "AAU-blocklist-DK-analysis/1.0")
    request = urllib.request.Request(url, headers={"User-Agent": agent, "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read(10_000_001)
                if len(body) > 10_000_000:
                    raise ValueError("Unexpectedly large registry response")
            payload = json.loads(body)
            ranges = validate_evidence(payload, day)
            directory.mkdir(parents=True, exist_ok=True)
            name = stamp()
            raw = directory / (name + ".response.json")
            raw.write_bytes(body)
            meta = dict(country="DK", requested_date=day, query_time=payload["data"]["query_time"],
                        retrieved_at_utc=now(), url=url, response_file=raw.name, sha256=sha(raw),
                        ipv4_prefixes=len(payload["data"]["resources"]["ipv4"]),
                        ipv6_prefixes=len(payload["data"]["resources"]["ipv6"]))
            meta_path = directory / (name + ".metadata.json")
            json_write(meta_path, meta)
            meta.update(metadata_path=str(meta_path), response_path=str(raw))
            time.sleep(1)  # Sequential requests, cached on subsequent runs.
            return ranges, meta
        except (OSError, ValueError, KeyError, TypeError) as e:
            retryable = not isinstance(e, urllib.error.HTTPError) or e.code == 429 or e.code >= 500
            if attempt < 2 and retryable:
                time.sleep(2 ** (attempt + 1))
                continue
            issue(issues, "WARN", "registry_request_failed", f"{url}: {e}", day)
            return None, None


def make_frame(snap, ranges, meta, writer, dk_writer=None):
    full, partial, all_ip, other = set(), set(), set(), set()
    covered = {4: [], 6: []}
    labels = Counter()
    for key in sorted(snap.keys):
        kind, value = key
        if kind not in {"ip", "cidr"}:
            label, version, hits = "NOT_IP_IN_SCOPE", "", []
            other.add(key)
        else:
            all_ip.add(key)
            label, version, hits = ranges.match(key) if ranges else ("UNKNOWN_EVIDENCE", network(key).version, [])
            if label == "DK_FULL": full.add(key)
            if label == "DK_PARTIAL": partial.add(key)
            if hits: covered[version].extend(hits)
        labels[label] += 1
        record = dict(date=snap.day, source=snap.source, snapshot_id=snap.id,
                             indicator_type=kind, indicator=value, classification=label,
                             ip_version=version, matched_address_count=size(hits) if ranges and version else NA,
                             matched_DK_CIDRs=cidrs(hits, version) if hits else "",
                             evidence_query_time=meta["query_time"] if meta else "",
                             evidence_sha256=meta["sha256"] if meta else "")
        writer.writerow(record)
        if hits and dk_writer is not None:
            dk_writer.writerow(record)
    return dict(snap=snap, all=all_ip, other=other, full=full, partial=partial,
                dk=full | partial, ranges={v: merge(p) for v, p in covered.items()},
                labels=labels, evidence=bool(ranges))


def metrics(a, b):
    added, removed, common = b-a, a-b, a & b
    union = a | b
    return dict(previous_count=len(a), current_count=len(b), added_count=len(added),
                removed_count=len(removed), unchanged_count=len(common), net_change=len(b)-len(a),
                percent_change=round(100*(len(b)-len(a))/len(a), 4) if a else NA,
                jaccard=round(len(common)/len(union), 6) if union else NA)


def compare_dates(frames, a, b, source, changes=None):
    left, right = frames.get((source, a)), frames.get((source, b))
    base = dict(previous_date=a, current_date=b, source=source,
                calendar_gap_days=(date.fromisoformat(b)-date.fromisoformat(a)).days)
    rows = []
    for scope, set_name in [("GLOBAL_IP_CIDR", "all"), ("DK_FULL", "full"), ("DK_ANY_MATCH", "dk")]:
        usable = bool(left and right and (set_name == "all" or left["evidence"] and right["evidence"]))
        row = dict(base, scope=scope, status="compared" if usable else "unknown_missing_input")
        if not usable:
            row.update({k: NA for k in metrics(set(), set())})
            row.update(feed_added=NA, feed_removed=NA, registry_scope_entered=NA, registry_scope_left=NA)
        else:
            x, y = left[set_name], right[set_name]
            row.update(metrics(x, y))
            row.update(feed_added=len((y-x)-left["all"]), feed_removed=len((x-y)-right["all"]),
                       registry_scope_entered=len((y-x) & left["all"]), registry_scope_left=len((x-y) & right["all"]))
            assert row["added_count"] + row["unchanged_count"] == row["current_count"]
            assert row["removed_count"] + row["unchanged_count"] == row["previous_count"]
            if changes is not None and set_name == "dk":
                for action, keys in [("added", y-x), ("removed", x-y)]:
                    for kind, indicator in sorted(keys):
                        in_other_feed = (kind, indicator) in (left["all"] if action == "added" else right["all"])
                        cause = "registry_scope_changed" if in_other_feed else "feed_membership_changed"
                        changes.writerow(dict(base, indicator_type=kind, indicator=indicator,
                                              change=action, cause=cause))
        rows.append(row)
    return rows


def persistence(frames, days, sources):
    rows = []
    for source in sources:
        for scope in ("GLOBAL_IP_CIDR", "DK_ANY_MATCH"):
            field_name = "all" if scope == "GLOBAL_IP_CIDR" else "dk"
            valid = [i for i, d in enumerate(days) if (source, d) in frames and
                     (field_name == "all" or frames[(source, d)]["evidence"])]
            appearances = defaultdict(list)
            for position, i in enumerate(valid):
                for key in frames[(source, days[i])][field_name]:
                    appearances[key].append((position, i))
            for (kind, value), hits in sorted(appearances.items()):
                reappearances = sum(p2 > p1+1 for (p1, _), (p2, _) in zip(hits, hits[1:]))
                max_run = run = 1
                for (_, i), (_, j) in zip(hits, hits[1:]):
                    run = run+1 if j == i+1 else 1
                    max_run = max(max_run, run)
                first, last = hits[0][1], hits[-1][1]
                rows.append(dict(source=source, scope=scope, indicator_type=kind, indicator=value,
                                 first_observed_date=days[first], last_observed_date=days[last],
                                 present_sampled_days=len(hits), eligible_sampled_days=len(valid),
                                 present_fraction=round(len(hits)/len(valid), 6),
                                 longest_consecutive_calendar_presence=max_run,
                                 observed_reappearances_after_sampled_absence=reappearances,
                                 left_censored_or_gap=first == 0 or first-1 not in valid,
                                 right_censored_or_gap=last == len(days)-1 or last+1 not in valid))
    return rows


def overlap_and_exclusive(frames, days, sources):
    overlaps, exclusive = [], []
    for day in days:
        for source_a, source_b in itertools.combinations(sources, 2):
            a, b = frames.get((source_a, day)), frames.get((source_b, day))
            valid = bool(a and b and a["evidence"] and b["evidence"])
            row = dict(date=day, source_a=source_a, source_b=source_b,
                       status="compared" if valid else "unknown_missing_input")
            row.update(exact_DK_key_overlap=len(a["dk"] & b["dk"]) if valid else NA,
                       exact_DK_key_jaccard=metrics(a["dk"], b["dk"])["jaccard"] if valid else NA)
            for v in (4, 6):
                row[f"overlapping_DK_ipv{v}_addresses"] = size(intersection(a["ranges"][v], b["ranges"][v])) if valid else NA
            overlaps.append(row)
        valid = all((s, day) in frames and frames[(s, day)]["evidence"] for s in sources)
        for source in sources:
            row = dict(date=day, source=source, status="compared" if valid else "unknown_missing_input")
            if valid:
                a = frames[(source, day)]
                other = [frames[(s, day)] for s in sources if s != source]
                row["exclusive_DK_exact_keys"] = len(a["dk"] - set().union(*(o["dk"] for o in other)))
                for v in (4, 6):
                    combined = merge(p for o in other for p in o["ranges"][v])
                    row[f"exclusive_DK_ipv{v}_addresses"] = size(a["ranges"][v])-size(intersection(a["ranges"][v], combined))
            else:
                row.update(exclusive_DK_exact_keys=NA, exclusive_DK_ipv4_addresses=NA, exclusive_DK_ipv6_addresses=NA)
            exclusive.append(row)
    return overlaps, exclusive


def address_changes(frames, days, sources):
    rows = []
    for a, b in zip(days, days[1:]):
        for source in sources:
            x, y = frames.get((source, a)), frames.get((source, b))
            valid = bool(x and y and x["evidence"] and y["evidence"])
            for v in (4, 6):
                row = dict(previous_date=a, current_date=b, source=source, ip_version=v,
                           status="compared" if valid else "unknown_missing_input")
                if valid:
                    previous, current = size(x["ranges"][v]), size(y["ranges"][v])
                    common = size(intersection(x["ranges"][v], y["ranges"][v]))
                    row.update(previous_addresses=previous, current_addresses=current,
                               added_addresses=current-common, removed_addresses=previous-common,
                               unchanged_addresses=common, net_change=current-previous)
                else:
                    row.update({k: NA for k in ["previous_addresses", "current_addresses", "added_addresses", "removed_addresses", "unchanged_addresses", "net_change"]})
                rows.append(row)
    return rows


def fixed_registry_sensitivity(frames, registry, days, sources):
    # A fixed country map isolates feed changes from changing country maps.
    # It is a sensitivity comparison, not the primary historical estimate.
    available = [d for d in days if registry.get(d, (None,))[0] is not None]
    baseline = available[0] if available else ""
    ranges = registry[baseline][0] if baseline else None
    rows = []
    for day in days:
        for source in sources:
            frame = frames.get((source, day))
            fixed = sum(ranges.match(k)[0] in {"DK_FULL", "DK_PARTIAL"} for k in frame["all"]) if frame and ranges else NA
            dynamic = len(frame["dk"]) if frame and frame["evidence"] else NA
            rows.append(dict(date=day, source=source, fixed_registry_date=baseline,
                             fixed_registry_DK_any_match=fixed, dated_registry_DK_any_match=dynamic,
                             difference=dynamic-fixed if isinstance(dynamic, int) and isinstance(fixed, int) else NA))
    return rows


def chart_svg(rows, sources, days, field_name, title):
    """Exact SVG chart using integer values, preserving missing-day gaps."""
    w, h, left, top = 1040, 430, 80, 60
    plot_w, plot_h = 900, 280
    points = {(r["source"], r["date"]): r[field_name] for r in rows}
    values = [v for v in points.values() if isinstance(v, int)]
    maximum = max(values, default=1) or 1
    e = html.escape
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="{e(title)}">',
           '<rect width="100%" height="100%" fill="white"/>',
           f'<text x="30" y="30" font-family="sans-serif" font-size="20">{e(title)}</text>']
    for i in range(5):
        y = top + plot_h - i*plot_h/4
        svg += [f'<path d="M{left} {y} H{left+plot_w}" stroke="#ddd"/>',
                f'<text x="{left-8}" y="{y+4}" text-anchor="end" font-size="12">{maximum*i/4:g}</text>']
    colours = ["#1261a0", "#a64b00", "#067c59", "#8b3893", "#554400", "#555555"]
    for j, source in enumerate(sources):
        previous = None; colour = colours[j % len(colours)]
        for i, day in enumerate(days):
            value = points.get((source, day))
            if not isinstance(value, int):
                previous = None; continue
            x = left + plot_w*i/max(1, len(days)-1); y = top+plot_h-plot_h*value/maximum
            if previous:
                svg.append(f'<path d="M{previous[0]} {previous[1]} L{x} {y}" fill="none" stroke="{colour}" stroke-width="2"/>')
            svg.append(f'<circle cx="{x}" cy="{y}" r="3" fill="{colour}"><title>{e(source)} {day}: {value}</title></circle>')
            previous = (x, y)
        svg.append(f'<text x="{left+j*220}" y="400" fill="{colour}" font-family="sans-serif" font-size="14">{e(source)}</text>')
    step = max(1, len(days)//7)
    for i in sorted(set(range(0, len(days), step)) | {len(days)-1}):
        x = left+plot_w*i/max(1, len(days)-1)
        svg.append(f'<text x="{x}" y="365" text-anchor="middle" font-size="12">{days[i]}</text>')
    return "\n".join(svg + ['</svg>'])


def table_html(rows, fields, limit=100):
    e = lambda x: html.escape(str(x))
    return '<table><thead><tr>'+''.join(f'<th>{e(k)}</th>' for k in fields)+'</tr></thead><tbody>'+''.join(
        '<tr>'+''.join(f'<td>{e(r.get(k, ""))}</td>' for k in fields)+'</tr>' for r in rows[:limit])+'</tbody></table>'


def write_report(out, run, daily, issues, changes):
    e = html.escape
    text = f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Danish blocklist analysis</title>
<style>body{{max-width:1150px;margin:35px auto;padding:0 20px;font:16px/1.5 system-ui;color:#172535}}h1,h2{{color:#164d71}}table{{border-collapse:collapse;font-size:12px;display:block;overflow:auto}}td,th{{border:1px solid #ccc;padding:7px;text-align:left}}th{{background:#eaf0f5}}img{{width:100%}}.status{{background:#fff1cb;padding:14px}}code{{overflow-wrap:anywhere}}@media print{{table{{font-size:9px}}h2{{break-after:avoid}}}}</style>
<h1>Danish registry-associated indicators in public blocklists</h1>
<p class="status"><b>{e(run['readiness'])}</b><br>Run: {e(run['run_id'])}<br>Generated: {run['generated_at_utc']}</p>
<p>Window: {run['start_date']} to {run['end_date']}. Calendar days: {run['calendar_days']};
 dates with usable normalized data: {run['observed_dates']}; dates with all expected feeds and dated DK evidence: {run['complete_dates']}.
 Target: {run['minimum_days']} complete sampled dates. Reaching this target does not finish the other research tasks.</p>
<nav><a href="#method">Method</a> · <a href="#findings">Results</a> · <a href="#gaps">Missing evidence</a> · <a href="#files">Files</a></nav>
<h2 id="method">What these results mean</h2>
<p>The input is the project's saved observations.csv. We choose the latest unambiguous normalized snapshot per source and UTC date,
 then compare its IP addresses and CIDRs with a dated DK country-resource list from RIPEstat. A known newer download without normalized rows blocks that day's analysis.
 Failed requests and missing data are not treated as empty feeds. Duplicate rows within a snapshot are counted once.</p>
<p><b>DK_FULL</b>: the entire entry is within DK-associated registry ranges. <b>DK_PARTIAL</b>: only part of a CIDR overlaps those ranges.
 <b>NO_DK_MATCH</b>: no match under this registry rule; it does not prove the address is outside Denmark.
 <b>UNKNOWN_EVIDENCE</b>: dated evidence is unavailable. Domains and URLs are retained in the audit but not classified by an IP country rule.</p>
<p>This is administrative registry association, not verified physical location, nationality, or evidence of malicious activity.
 The RIPEstat query is dated at midnight; collection occurs later in the day and underlying RIR files may have different update times.
 It is not a census of all Danish IPs. CIDRs count as entries in indicator metrics; address coverage is deduplicated separately for IPv4 and IPv6.</p>
<h2 id="findings">Daily findings</h2>
<img src="dk_indicators.svg" alt="DK full and partial entry trend by provider; missing dates break lines">
<p>The figure counts entries with any DK overlap. The table separates full and partial matches; see <a href="daily_summary.csv">daily_summary.csv</a> for every column.</p>'''
    text += table_html(daily, ["date", "source", "status", "global_ip_cidr", "DK_full", "DK_partial", "unknown", "DK_ipv4_addresses"], 150)
    text += '<h2>Global context</h2><img src="global_indicators.svg" alt="Global IP and CIDR entries per day">'
    text += '<h2>Changes between adjacent calendar days</h2><p>Added/removed means observed set membership changed between two samples. '
    text += 'It does not establish an attack, a false positive, or a completed delisting request. Changes caused only by registry classification are separated. '
    text += 'NA in percent change also occurs when the earlier count is zero. All-pairs comparisons are in a separate folder and must not be summed across overlapping periods.</p>'
    text += table_html([r for r in changes if r["scope"] == "DK_ANY_MATCH"],
                       ["previous_date", "current_date", "source", "status", "added_count", "removed_count", "registry_scope_entered", "registry_scope_left"], 100)
    text += '''<h2>Persistence, overlap and uncertainty</h2><p>Persistence is the number of sampled days present divided by eligible sampled days, not the true duration of listing.
 Reappearance requires a sampled absence between two presences. Unobserved days remain unknown; consecutive streaks break at gaps.
 Boundary and gap censoring flags are provided. In DK scope, registry changes can change presence independently of feed membership.</p>
<p>Overlap is measured both with exact (type, indicator) keys and with covered address ranges, so a host inside another provider's CIDR is recognised by address overlap.
 Exact keys may differ while covering the same space. Exclusive contribution is relative to the chosen feeds, not the whole Internet.
 FireHOL aggregates upstream sources, so provider outputs must not be assumed independent. Address coverage describes listed space, not active hosts or attack counts.</p>
<p>Address-space changes are reported separately from entry changes. A CIDR split or merge can change entry counts without changing covered addresses.
 fixed_registry_sensitivity.csv also repeats the classification with the earliest available country map held constant. Differences from the dated classification
 show sensitivity to the country map; this fixed map is not substituted for historical evidence.</p>
<h2 id="gaps">What remains missing</h2><p>The extension can request dated registry evidence for existing saved observations.
 It cannot recreate blocklist downloads that were never collected. It does not supply independent reputation verdicts, historic DNS ownership,
 false-positive ground truth, provider-policy research, a PRISMA search record, or an authorised listing/delisting case.</p>
<p>Large changes are flagged for investigation; their cause is not inferred. Missing raw files weaken provenance; hash mismatches block the affected snapshots.
 The current normalization parser may have omitted unsupported lines before this extension runs. Review raw formats and parser notes separately.</p>'''
    text += table_html(issues, ["severity", "code", "date", "source", "detail"], 100)
    text += '<p>All issues, including those beyond this preview, are in <a href="audit_issues.csv">audit_issues.csv</a>.</p>'
    text += '<h2 id="files">Complete evidence files</h2><ul>'
    for p in sorted(out.rglob("*")):
        if p.is_file():
            rel = p.relative_to(out).as_posix()
            text += f'<li><a href="{urllib.parse.quote(rel)}">{e(rel)}</a></li>'
    text += '''</ul><p><a href="run_manifest.json">run_manifest.json</a> records the input and script checksums, and every generated output checksum.
 Evidence URLs, retrieval times and checksums are in evidence_index.csv. Snapshot selection and raw provenance are in snapshot_index.csv.</p>
<h2>Method references</h2><p>[1] RIPE NCC, <a href="https://data.stat.ripe.net/docs/data-api/api-endpoints/country-resource-list">Country Resource List API documentation</a>.
 [2] RIPE NCC, <a href="https://labs.ripe.net/author/kjerstin-burdiek/country-codes-in-the-ripe-database/">Country Codes in the RIPE Database</a>, 2023.
 Access dates and requested dates for actual evidence appear in the evidence index.</p></html>'''
    (out / "report.html").write_text(text, encoding="utf-8")


def run(args):
    root = args.root.resolve()
    input_path = (root / args.input).resolve()
    if not input_path.is_file():
        raise ValueError(f"Missing normalized observations: {input_path}. Run the existing normalizer first.")
    before = sha(input_path)
    log_path = root / "logs/collection_log.csv"
    log_before = sha(log_path) if log_path.is_file() else None
    issues = []
    print("Reading saved observations and checking snapshot provenance...", flush=True)
    selected, index = load_snapshots(root, input_path, issues)
    observed = sorted({d for _, d in selected})
    days = calendar(args.start or observed[0], args.end or observed[-1])
    if args.end and args.end > datetime.now(timezone.utc).date().isoformat():
        raise ValueError("Study end date is in the future")
    sources = sorted(set(args.sources.split(",")) | {s for s, _ in selected}) if args.sources else sorted(set(DEFAULT_SOURCES) | {s for s, _ in selected})
    run_id = stamp() + ("_audit" if args.audit else "_danish")
    out = root / "danish_analysis" / run_id
    out.mkdir(parents=True, exist_ok=False)
    json_write(out / "run_status.json", dict(status="running", run_id=run_id, started_utc=now()))
    print(f"Output folder: {out}", flush=True)
    print(f"Window: {days[0]} to {days[-1]} | {len(days)} calendar days | sources: {', '.join(sources)}", flush=True)
    registry, evidence_index = {}, []
    for day in days:
        if not any((s, day) in selected and not selected[(s, day)].blocked for s in sources):
            continue
        print(f"Evidence {day}: {'fetch/cache' if args.fetch and not args.audit else 'saved cache only'}", flush=True)
        ranges, meta = evidence_for_day(root, day, args.fetch and not args.audit, issues)
        registry[day] = (ranges, meta)
        if meta: evidence_index.append(meta)
    frames, daily, coverage = {}, [], []
    fields = ["date", "source", "snapshot_id", "indicator_type", "indicator", "classification", "ip_version",
              "matched_address_count", "matched_DK_CIDRs", "evidence_query_time", "evidence_sha256"]
    with (out / "classified_observations.csv").open("w", newline="", encoding="utf-8") as f, (out / "danish_indicators.csv").open("w", newline="", encoding="utf-8") as dk_f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
        dk_writer = csv.DictWriter(dk_f, fieldnames=fields); dk_writer.writeheader()
        for day in days:
            for source in sources:
                snap = selected.get((source, day))
                usable = bool(snap and not snap.blocked)
                ranges, meta = registry.get(day, (None, None))
                coverage.append(dict(date=day, source=source, normalized_snapshot_available=bool(snap),
                                     snapshot_usable=usable, dated_DK_evidence=bool(ranges),
                                     raw_status=snap.raw_status if snap else "missing",
                                     reason=snap.blocked if snap else "no_normalized_snapshot"))
                row = dict(date=day, source=source, status="usable" if usable else "missing_or_blocked", global_ip_cidr=NA,
                           DK_full=NA, DK_partial=NA, DK_any_match=NA, no_DK_match=NA, unknown=NA, non_IP_entries=NA,
                           DK_ipv4_addresses=NA, DK_ipv6_addresses=NA, registry_classification_coverage_pct=NA)
                if usable:
                    frame = make_frame(snap, ranges, meta, writer, dk_writer)
                    frames[(source, day)] = frame
                    row.update(global_ip_cidr=len(frame["all"]), non_IP_entries=len(frame["other"]),
                               unknown=frame["labels"]["UNKNOWN_EVIDENCE"],
                               registry_classification_coverage_pct=100 if ranges and frame["all"] else 0 if frame["all"] else NA)
                    if ranges:
                        row.update(DK_full=len(frame["full"]), DK_partial=len(frame["partial"]), DK_any_match=len(frame["dk"]),
                                   no_DK_match=frame["labels"]["NO_DK_MATCH"],
                                   DK_ipv4_addresses=size(frame["ranges"][4]), DK_ipv6_addresses=size(frame["ranges"][6]))
                        assert len(frame["full"])+len(frame["partial"])+row["no_DK_match"] == len(frame["all"])
                else:
                    issue(issues, "WARN", "source_day_unavailable", row["status"], day, source)
                daily.append(row)
    csv_write(out / "daily_summary.csv", daily)
    csv_write(out / "coverage.csv", coverage)
    csv_write(out / "snapshot_index.csv", index)
    evidence_fields = ["country", "requested_date", "query_time", "retrieved_at_utc", "url", "response_file", "sha256",
                       "ipv4_prefixes", "ipv6_prefixes", "metadata_path", "response_path"]
    csv_write(out / "evidence_index.csv", evidence_index, evidence_fields)
    comparisons = out / "comparisons"; comparisons.mkdir()
    change_fields = ["previous_date", "current_date", "source", "calendar_gap_days", "indicator_type", "indicator", "change", "cause"]
    adjacent = []
    with (comparisons / "daily_DK_indicator_changes.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=change_fields); writer.writeheader()
        for a, b in zip(days, days[1:]):
            for source in sources: adjacent.extend(compare_dates(frames, a, b, source, writer))
    comparison_fields = list(compare_dates({}, days[0], days[-1], sources[0])[0])
    csv_write(comparisons / "daily_comparisons.csv", adjacent, comparison_fields)
    pairs = []
    observed_in_window = [d for d in days if any((s, d) in frames for s in sources)]
    for a, b in itertools.combinations(observed_in_window, 2):
        for source in sources: pairs.extend(compare_dates(frames, a, b, source))
    csv_write(comparisons / "all_date_pairs.csv", pairs, comparison_fields)
    csv_write(comparisons / "first_vs_last.csv", [r for r in pairs if r["previous_date"] == days[0] and r["current_date"] == days[-1]], comparison_fields)
    csv_write(comparisons / "address_space_changes.csv", address_changes(frames, days, sources),
              ["previous_date", "current_date", "source", "ip_version", "status", "previous_addresses", "current_addresses", "added_addresses", "removed_addresses", "unchanged_addresses", "net_change"])
    csv_write(out / "fixed_registry_sensitivity.csv", fixed_registry_sensitivity(frames, registry, days, sources))
    for row in adjacent:
        if row["scope"] == "GLOBAL_IP_CIDR" and isinstance(row["percent_change"], (int, float)) and abs(row["percent_change"]) >= 40:
            issue(issues, "WARN", "large_count_change_review", f"{row['percent_change']}% from {row['previous_date']}; check feed/logs/parser before explaining cause", row["current_date"], row["source"])
    print("Calculating persistence, range overlap and exclusive contribution...", flush=True)
    csv_write(out / "persistence.csv", persistence(frames, days, sources),
              ["source", "scope", "indicator_type", "indicator", "first_observed_date", "last_observed_date", "present_sampled_days", "eligible_sampled_days", "present_fraction", "longest_consecutive_calendar_presence", "observed_reappearances_after_sampled_absence", "left_censored_or_gap", "right_censored_or_gap"])
    overlap, exclusive = overlap_and_exclusive(frames, days, sources)
    csv_write(out / "overlap.csv", overlap, ["date", "source_a", "source_b", "status", "exact_DK_key_overlap", "exact_DK_key_jaccard", "overlapping_DK_ipv4_addresses", "overlapping_DK_ipv6_addresses"])
    csv_write(out / "exclusive_contribution.csv", exclusive)
    if sha(input_path) != before:
        issue(issues, "ERROR", "input_changed_during_analysis", "Do not collect or normalize concurrently; rerun after the original pipeline completes")
    if (sha(log_path) if log_path.is_file() else None) != log_before:
        issue(issues, "ERROR", "collection_log_changed_during_analysis", "Collection log changed during analysis; rerun when collection is finished")
    complete = sum(all((s, d) in frames and frames[(s, d)]["evidence"] for s in sources) for d in days)
    if complete < args.minimum_days:
        issue(issues, "WARN", "month_scale_coverage_incomplete", f"{complete} complete dates; target {args.minimum_days}. Repeated same-day runs do not add dates.")
    if not any(f["other"] for f in frames.values()):
        issue(issues, "INFO", "domain_study_not_present", "These saved observations contain IP/CIDR entries, not domain evidence")
    issue(issues, "INFO", "additional_research_required", "Provider policies, independent enrichment if included, PRISMA record and authorised delisting cases are separate research inputs")
    csv_write(out / "audit_issues.csv", issues, ["severity", "code", "date", "source", "detail"])
    errors = sum(r["severity"] == "ERROR" for r in issues)
    warnings = sum(r["severity"] == "WARN" for r in issues)
    readiness = "BLOCKED INPUTS / PARTIAL ANALYSIS" if errors else "INTERIM — COVERAGE INCOMPLETE" if complete < args.minimum_days else "MONTH-SCALE DATA AVAILABLE — REVIEW LIMITATIONS"
    run_info = dict(version=VERSION, run_id=run_id, generated_at_utc=now(), start_date=days[0], end_date=days[-1],
                    calendar_days=len(days), observed_dates=len(observed_in_window), complete_dates=complete,
                    minimum_days=args.minimum_days, expected_sources=sources, errors=errors, warnings=warnings,
                    readiness=readiness, input_file=str(input_path), input_sha256=before, script_sha256=sha(__file__),
                    collection_log_file=str(log_path), collection_log_sha256=log_before,
                    selection="latest unambiguous normalized source/day snapshot; newer unnormalized success blocks fallback",
                    DK_definition="dated DK association in RIR statistics via RIPEstat; not physical geolocation",
                    evidence_query_dates=[r["requested_date"] for r in evidence_index],
                    evidence_retrieval_is_retrospective=True, network_enabled=bool(args.fetch and not args.audit))
    for column, filename, title in [("DK_any_match", "dk_indicators.svg", "Entries overlapping dated DK registry ranges"),
                                     ("global_ip_cidr", "global_indicators.svg", "Global IP/CIDR entries in selected snapshots")]:
        (out / filename).write_text(chart_svg(daily, sources, days, column, title), encoding="utf-8")
    json_write(out / "validation.json", dict(errors=errors, warnings=warnings, complete_dates=complete,
                                             status="failed" if errors else "passed_with_warnings" if warnings else "passed",
                                             checks=["schema", "snapshot metadata", "raw checksums when available", "dated evidence checksums",
                                                     "classification partition", "comparison set identities", "input unchanged"]))
    json_write(out / "run_status.json", dict(status="completed_with_errors" if errors else "completed", run_id=run_id, completed_utc=now()))
    write_report(out, run_info, daily, issues, adjacent)
    run_info["output_sha256"] = {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}
    json_write(out / "run_manifest.json", run_info)
    print(f"\n{readiness}\nComplete dates: {complete}/{args.minimum_days}; errors: {errors}; warnings: {warnings}")
    print(f"READ REPORT: {out / 'report.html'}\nCHECK MISSING DATA: {out / 'audit_issues.csv'}\nCOMPARE DATES: {comparisons / 'all_date_pairs.csv'}")
    return out


def show_runs(root):
    runs = sorted((root / "danish_analysis").glob("*/run_manifest.json"), reverse=True)
    for i, path in enumerate(runs, 1):
        try:
            r = json.loads(path.read_text(encoding="utf-8"))
            print(f"{i}. {r['start_date']} -> {r['end_date']} | complete dates {r['complete_dates']} | {path.parent.name}")
        except (ValueError, KeyError):
            print(f"{i}. unreadable manifest: {path}")
    return runs


def menu():
    while True:
        print("\nDANISH STUDY — saved observations, dated evidence and separate reports")
        print("1. Check available data and missing evidence (offline)")
        print("2. Fetch missing dated DK evidence and analyse all saved dates")
        print("3. Analyse again using cached evidence only (offline)")
        print("4. List reports and show the exact folder for a selected report")
        print("5. Open the original project menu (collection and previous tools)")
        print("0. Exit")
        choice = input("Choose: ").strip()
        if choice == "0": return
        if choice in {"1", "2", "3"}:
            start = input("Start UTC date YYYY-MM-DD, or Enter for earliest saved: ").strip()
            end = input("End UTC date YYYY-MM-DD, or Enter for latest saved: ").strip()
            argv = [sys.executable, str(Path(__file__).resolve())]
            if choice == "1": argv += ["--audit"]
            if choice == "2": argv += ["--fetch"]
            if start: argv += ["--start", start]
            if end: argv += ["--end", end]
            subprocess.run(argv, cwd=ROOT, check=False)
        elif choice == "4":
            runs = show_runs(ROOT)
            value = input("Report number, or Enter to return: ").strip()
            if value.isdigit() and 1 <= int(value) <= len(runs):
                print("Report:", runs[int(value)-1].parent / "report.html")
                print("Folder:", runs[int(value)-1].parent)
        elif choice == "5":
            path = ROOT / "scripts/project_menu.py"
            if path.is_file(): subprocess.run([sys.executable, str(path)], cwd=ROOT, check=False)
            else: print("Original menu not found:", path)
        else:
            print("Choose a number shown above.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--input", type=Path, default=Path("data/normalized/observations.csv"))
    parser.add_argument("--start", help="First UTC date; includes gaps in the requested window")
    parser.add_argument("--end", help="Last UTC date; includes gaps in the requested window")
    parser.add_argument("--sources", help="Comma-separated expected source names; default FireHOL,Spamhaus DROP,blocklist.de")
    parser.add_argument("--minimum-days", type=int, default=30, help="Project planning target; not a guarantee of scientific completeness")
    parser.add_argument("--fetch", action="store_true", help="Request dated DK registry lists only; never scan listed IPs")
    parser.add_argument("--audit", action="store_true", help="Use only saved data/evidence; never make network requests")
    parser.add_argument("--menu", action="store_true")
    parser.add_argument("--list-runs", action="store_true")
    args = parser.parse_args()
    if args.minimum_days < 1: parser.error("--minimum-days must be positive")
    if args.audit and args.fetch: parser.error("Choose --audit or --fetch, not both")
    try:
        if args.menu: menu()
        elif args.list_runs: show_runs(args.root.resolve())
        else:
            out = run(args)
            if json.loads((out / "validation.json").read_text())["errors"]:
                return 2
    except (OSError, ValueError, KeyError, csv.Error) as exc:
        print(f"ERROR: {exc}\nOriginal project files have not been changed. Inspect any incomplete run folder before rerunning.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
