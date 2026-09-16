#!/usr/bin/env python3
"""Normalize the supported raw feed shapes while preserving provenance."""

from __future__ import annotations

import argparse
import csv
import hashlib
import ipaddress
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


FIELDS = [
    "snapshot_id",
    "source_name",
    "retrieved_at_utc",
    "source_path",
    "sha256",
    "indicator_type",
    "indicator",
    "source_value",
    "reason",
    "provider_timestamp",
    "country_class",
    "first_seen",
    "last_seen",
    "status",
    "notes",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def timestamp_from_name(path: Path) -> str:
    match = re.search(r"(\d{8}T\d{6}Z)", path.name)
    if match:
        value = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ")
        return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def snapshot_id(path: Path, retrieved_at: str) -> str:
    stamp = re.search(r"(\d{8}T\d{6}Z)", path.name)
    if stamp:
        # The collection script already places the UTC stamp in every file
        # name. Keeping the complete stem avoids duplicating that stamp.
        return path.stem
    return f"{path.stem}_{retrieved_at.replace(':', '').replace('-', '')}"


def canonical_ip_or_cidr(value: str) -> tuple[str, str] | None:
    candidate = value.strip()
    try:
        if "/" in candidate:
            return "cidr", str(ipaddress.ip_network(candidate, strict=False))
        return "ip", str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def row(meta: dict[str, str], indicator_type: str, indicator: str, source_value: str, **extra: str) -> dict[str, str]:
    result = {key: "" for key in FIELDS}
    result.update(meta)
    result.update(
        {
            "indicator_type": indicator_type,
            "indicator": indicator,
            "source_value": source_value,
            "country_class": "Unknown",
            "status": "listed",
        }
    )
    result.update(extra)
    return result


def base_meta(path: Path, source_name: str, digest: str, retrieved_at: str) -> dict[str, str]:
    return {
        "snapshot_id": snapshot_id(path, retrieved_at),
        "source_name": source_name,
        "retrieved_at_utc": retrieved_at,
        "source_path": str(path),
        "sha256": digest,
    }


def parse_firehol(path: Path, meta: dict[str, str]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for line_number, line in enumerate(path.read_text(errors="replace").splitlines(), start=1):
        content = line.split("#", 1)[0].strip()
        if not content or content.startswith(";"):
            continue
        parsed = canonical_ip_or_cidr(content)
        if parsed:
            kind, value = parsed
            records.append(row(meta, kind, value, content, notes=f"line {line_number}"))
    return records


def parse_blocklist_de(path: Path, meta: dict[str, str]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for line_number, line in enumerate(path.read_text(errors="replace").splitlines(), start=1):
        content = line.split("#", 1)[0].strip()
        if not content:
            continue
        parsed = canonical_ip_or_cidr(content)
        if parsed:
            kind, value = parsed
            records.append(row(meta, kind, value, content, notes=f"line {line_number}"))
    return records


def json_value(item: dict, names: tuple[str, ...]) -> str:
    for name in names:
        value = item.get(name)
        if value not in (None, ""):
            return str(value)
    return ""


def parse_spamhaus(path: Path, meta: dict[str, str]) -> list[dict[str, str]]:
    text = path.read_text(errors="replace")
    try:
        payload = json.loads(text)
        items = payload.get("blocklist") or payload.get("data") or payload.get("entries") or []
    except json.JSONDecodeError:
        # The current Spamhaus DROP endpoint is newline-delimited JSON even
        # though its filename ends in .json. Support both documented shapes.
        items = [
            json.loads(line)
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    if isinstance(items, dict):
        items = items.values()
    records: list[dict[str, str]] = []
    for item in items:
        if isinstance(item, str):
            value = item
            reason = ""
            provider_timestamp = ""
        else:
            value = json_value(item, ("cidr", "ip", "ip_address", "range", "network"))
            reason = json_value(item, ("sblid", "reason", "rir", "as", "asn"))
            provider_timestamp = json_value(item, ("timestamp", "last_seen", "first_seen", "date"))
        parsed = canonical_ip_or_cidr(value)
        if parsed:
            kind, canonical = parsed
            records.append(
                row(meta, kind, canonical, value, reason=reason, provider_timestamp=provider_timestamp)
            )
    return records


def domain_from_url(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"http://{value}")
    return (parsed.hostname or value).lower().rstrip(".")


def parse_urlhaus(path: Path, meta: dict[str, str]) -> list[dict[str, str]]:
    lines = [line for line in path.read_text(errors="replace").splitlines() if not line.startswith("#")]
    if not lines:
        return []
    reader = csv.DictReader(lines)
    records: list[dict[str, str]] = []
    for item in reader:
        url = (item.get("url") or "").strip()
        host = (item.get("host") or "").strip()
        value = url or host
        if not value:
            continue
        kind = "url" if url else "domain"
        indicator = value if kind == "url" else domain_from_url(value)
        records.append(
            row(
                meta,
                kind,
                indicator,
                value,
                reason=(item.get("threat") or "").strip(),
                provider_timestamp=(item.get("dateadded") or item.get("last_online") or "").strip(),
                notes=(item.get("url_status") or "").strip(),
            )
        )
    return records


def parse_file(path: Path) -> list[dict[str, str]]:
    lower = path.name.lower()
    retrieved_at = timestamp_from_name(path)
    digest = sha256(path)
    if lower.startswith("firehol_") or "firehol" in lower:
        source = "FireHOL"
        meta = base_meta(path, source, digest, retrieved_at)
        return parse_firehol(path, meta)
    if lower.startswith("spamhaus_") or "spamhaus" in lower:
        source = "Spamhaus DROP"
        meta = base_meta(path, source, digest, retrieved_at)
        return parse_spamhaus(path, meta)
    if lower.startswith("blocklist_de_") or "blocklist" in lower:
        source = "blocklist.de"
        meta = base_meta(path, source, digest, retrieved_at)
        return parse_blocklist_de(path, meta)
    if lower.startswith("urlhaus_") or "urlhaus" in lower:
        source = "URLhaus"
        meta = base_meta(path, source, digest, retrieved_at)
        return parse_urlhaus(path, meta)
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--errors", type=Path, required=True)
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.errors.parent.mkdir(parents=True, exist_ok=True)
    errors: list[dict[str, str]] = []
    records: list[dict[str, str]] = []

    for path in sorted(args.raw_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            parsed = parse_file(path)
            records.extend(parsed)
            if not parsed:
                errors.append({"path": str(path), "error": "no supported records parsed"})
        except Exception as exc:  # keep processing other provider snapshots
            errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})

    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)
    with args.errors.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "error"])
        writer.writeheader()
        writer.writerows(errors)

    print(f"wrote {len(records)} normalized observations to {args.out}")
    print(f"wrote {len(errors)} parser notes to {args.errors}")


if __name__ == "__main__":
    main()
