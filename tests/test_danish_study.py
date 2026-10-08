"""Offline checks with synthetic documentation-address fixtures, never real findings."""
import argparse
import contextlib
import csv
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/danish_study.py"
spec = importlib.util.spec_from_file_location("danish_study", SCRIPT)
study = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = study
spec.loader.exec_module(study)


def evidence(root, day, prefixes=None):
    prefixes = prefixes if prefixes is not None else ["192.0.2.0/24", "198.51.100.0/25"]
    directory = root / "data/danish_registry_evidence" / day
    directory.mkdir(parents=True, exist_ok=True)
    raw = directory / "20261008T120000Z_fixture.response.json"
    payload = dict(status="ok", data=dict(query_time=day+"T00:00:00", resources=dict(ipv4=prefixes, ipv6=["2001:db8::/32"])))
    study.json_write(raw, payload)
    meta = dict(country="DK", requested_date=day, query_time=day+"T00:00:00", retrieved_at_utc="2026-10-08T12:00:00Z",
                url="synthetic-offline-test", response_file=raw.name, sha256=study.sha(raw), ipv4_prefixes=len(prefixes), ipv6_prefixes=1)
    study.json_write(directory / "20261008T120000Z_fixture.metadata.json", meta)
    return raw


def make_input(root, records):
    """records are (source, ISO timestamp, list of IPs/CIDRs)."""
    rows, logs = [], []
    for i, (source, ts, indicators) in enumerate(records):
        day = ts[:10]; sid = f"fixture_{i}_{ts.replace(':', '')}"
        raw = root / "data/raw" / day / (sid+".txt")
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text("\n".join(indicators)+"\n")
        digest = study.sha(raw)
        for value in indicators:
            rows.append(dict(snapshot_id=sid, source_name=source, retrieved_at_utc=ts, source_path=str(raw), sha256=digest,
                             indicator_type="cidr" if "/" in value else "ip", indicator=value))
        logs.append(dict(retrieved_at_utc=ts, source=source, url="synthetic-offline-test", http_status="200",
                         bytes=raw.stat().st_size, sha256=digest, path=str(raw), status="ok", notes="fixture"))
    path = root / "data/normalized/observations.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    study.csv_write(path, rows)
    (root / "logs").mkdir(exist_ok=True)
    study.csv_write(root / "logs/collection_log.csv", logs)
    return path


class DanishStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_full_partial_nonmatch_and_ipv6_without_expansion(self):
        ranges = study.Ranges(["192.0.2.0/25", "2001:db8::/32"])
        self.assertEqual(ranges.match(("ip", "192.0.2.1"))[0], "DK_FULL")
        label, version, hits = ranges.match(("cidr", "192.0.2.0/24"))
        self.assertEqual((label, version, study.size(hits)), ("DK_PARTIAL", 4, 128))
        self.assertEqual(ranges.match(("ip", "192.0.2.200"))[0], "NO_DK_MATCH")
        self.assertEqual(study.size(ranges.match(("cidr", "2001:db8::/32"))[2]), 2**96)

    def test_overlapping_ranges_do_not_double_count(self):
        ranges = study.Ranges(["192.0.2.0/24", "192.0.2.0/25"])
        self.assertEqual(study.size(ranges.match(("cidr", "192.0.2.0/24"))[2]), 256)

    def test_latest_snapshot_not_daily_union(self):
        make_input(self.root, [("FireHOL", "2026-09-16T06:00:00Z", ["192.0.2.1", "192.0.2.2"]),
                               ("FireHOL", "2026-09-16T12:00:00Z", ["192.0.2.3", "192.0.2.3"])])
        selected, index = study.load_snapshots(self.root, self.root / "data/normalized/observations.csv", [])
        self.assertEqual(selected[("FireHOL", "2026-09-16")].keys, {("ip", "192.0.2.3")})
        self.assertEqual([r["duplicate_rows"] for r in index if r["selected"]], [1])

    def test_unprocessed_newer_success_blocks_fallback(self):
        make_input(self.root, [("FireHOL", "2026-09-16T06:00:00Z", ["192.0.2.1"])])
        logs = list(study.csv_read(self.root / "logs/collection_log.csv"))
        logs.append(dict(logs[0], retrieved_at_utc="2026-09-16T12:00:00Z", sha256="different"))
        study.csv_write(self.root / "logs/collection_log.csv", logs)
        selected, _ = study.load_snapshots(self.root, self.root / "data/normalized/observations.csv", [])
        self.assertEqual(selected[("FireHOL", "2026-09-16")].blocked, "newer_download_not_normalized")

    def test_raw_hash_mismatch_blocks_snapshot(self):
        path = make_input(self.root, [("FireHOL", "2026-09-16T12:00:00Z", ["192.0.2.1"])])
        raw = next((self.root / "data/raw").rglob("*.txt")); raw.write_text("changed")
        selected, _ = study.load_snapshots(self.root, path, [])
        self.assertEqual(selected[("FireHOL", "2026-09-16")].blocked, "raw_hash_mismatch")

    def test_invalid_indicator_blocks_instead_of_becoming_removal(self):
        path = make_input(self.root, [("FireHOL", "2026-09-16T12:00:00Z", ["192.0.2.999"])])
        selected, _ = study.load_snapshots(self.root, path, [])
        self.assertEqual(selected[("FireHOL", "2026-09-16")].blocked, "invalid_or_conflicting_rows")

    def test_wrong_evidence_day_and_corruption_rejected(self):
        raw = evidence(self.root, "2026-09-16")
        payload = json.loads(raw.read_text())
        with self.assertRaises(ValueError): study.validate_evidence(payload, "2026-09-17")
        raw.write_text(raw.read_text()+" ")
        issues = []
        with patch.object(study.urllib.request, "urlopen", side_effect=AssertionError("Must stay offline")):
            result, _ = study.evidence_for_day(self.root, "2026-09-16", False, issues)
        self.assertIsNone(result)
        self.assertIn("invalid_evidence_cache", [r["code"] for r in issues])

    def test_missing_snapshot_is_unknown_not_removal(self):
        left = dict(all={("ip", "192.0.2.1")}, full=set(), dk=set(), evidence=True)
        rows = study.compare_dates({("FireHOL", "2026-09-16"): left}, "2026-09-16", "2026-09-17", "FireHOL")
        self.assertTrue(all(r["removed_count"] == "NA" for r in rows))

    def test_zero_baseline_percentage_undefined_but_comparison_valid(self):
        f = dict(all=set(), full=set(), dk=set(), evidence=True)
        rows = study.compare_dates({("s", "2026-09-16"): f, ("s", "2026-09-17"): f}, "2026-09-16", "2026-09-17", "s")
        self.assertEqual(rows[0]["status"], "compared")
        self.assertEqual(rows[0]["percent_change"], "NA")
        self.assertEqual(rows[0]["removed_count"], 0)

    def test_registry_only_change_is_not_feed_removal(self):
        key = ("ip", "192.0.2.1")
        left = dict(all={key}, full={key}, dk={key}, evidence=True)
        right = dict(all={key}, full=set(), dk=set(), evidence=True)
        rows = study.compare_dates({("s", "2026-09-16"): left, ("s", "2026-09-17"): right}, "2026-09-16", "2026-09-17", "s")
        self.assertEqual(rows[2]["registry_scope_left"], 1)
        self.assertEqual(rows[2]["feed_removed"], 0)

    def test_reappearance_requires_sampled_absence(self):
        key = ("ip", "192.0.2.1")
        yes = dict(all={key}, dk={key}, evidence=True)
        no = dict(all=set(), dk=set(), evidence=True)
        days = study.calendar("2026-09-16", "2026-09-19")
        frames = {("s", days[0]): yes, ("s", days[2]): yes, ("s", days[3]): yes}
        self.assertEqual(study.persistence(frames, days, ["s"])[0]["observed_reappearances_after_sampled_absence"], 0)
        frames[("s", days[1])] = no
        result = study.persistence(frames, days, ["s"])[0]
        self.assertEqual(result["observed_reappearances_after_sampled_absence"], 1)
        self.assertEqual(result["longest_consecutive_calendar_presence"], 2)

    def test_exact_keys_and_address_overlap_are_different(self):
        a = dict(dk={("ip", "192.0.2.1")}, evidence=True, ranges={4: [(3221225985, 3221225985)], 6: []})
        b = dict(dk={("cidr", "192.0.2.0/24")}, evidence=True, ranges={4: [(3221225984, 3221226239)], 6: []})
        overlap, exclusive = study.overlap_and_exclusive({("a", "2026-09-16"): a, ("b", "2026-09-16"): b}, ["2026-09-16"], ["a", "b"])
        self.assertEqual(overlap[0]["exact_DK_key_overlap"], 0)
        self.assertEqual(overlap[0]["overlapping_DK_ipv4_addresses"], 1)
        self.assertEqual(exclusive[0]["exclusive_DK_ipv4_addresses"], 0)

    def test_portable_raw_path_and_traversal_rejection(self):
        old = "/Users/sam/Old Project/data/raw/2026-09-16/a.txt"
        self.assertEqual(study.local_raw(self.root, old), (self.root / "data/raw/2026-09-16/a.txt").resolve())
        self.assertIsNone(study.local_raw(self.root, "data/raw/../../../secret"))

    def test_full_offline_run_preserves_inputs_and_reconciles_outputs(self):
        records = [
            ("FireHOL", "2026-09-16T06:00:00Z", ["192.0.2.99"]),
            ("FireHOL", "2026-09-16T12:00:00Z", ["192.0.2.1", "198.51.100.0/24", "203.0.113.1"]),
            ("FireHOL", "2026-09-17T12:00:00Z", ["192.0.2.1", "198.51.100.0/24", "198.51.100.129"]),
            ("FireHOL", "2026-09-19T12:00:00Z", ["192.0.2.1"]),
            ("blocklist.de", "2026-09-16T12:00:00Z", ["192.0.2.1"]),
            ("blocklist.de", "2026-09-17T12:00:00Z", ["192.0.2.1"])]
        input_path = make_input(self.root, records)
        evidence(self.root, "2026-09-16")
        evidence(self.root, "2026-09-17", ["198.51.100.0/24"])
        # September 19 deliberately has no registry cache.
        before = {str(p): study.sha(p) for p in self.root.rglob("*") if p.is_file()}
        args = argparse.Namespace(root=self.root, input=Path("data/normalized/observations.csv"), start=None, end=None,
                                  sources="FireHOL,blocklist.de", minimum_days=30, fetch=False, audit=True)
        with patch.object(study.urllib.request, "urlopen", side_effect=AssertionError("Must stay offline")), contextlib.redirect_stdout(io.StringIO()):
            out = study.run(args)
        self.assertTrue(all(study.sha(p) == digest for p, digest in before.items()))
        daily = list(study.csv_read(out / "daily_summary.csv"))
        first = next(r for r in daily if r["date"] == "2026-09-16" and r["source"] == "FireHOL")
        self.assertEqual((first["DK_full"], first["DK_partial"], first["DK_ipv4_addresses"]), ("1", "1", "129"))
        self.assertTrue(all(r["DK_full"] == "NA" for r in daily if r["date"] == "2026-09-18"))
        last = next(r for r in daily if r["date"] == "2026-09-19" and r["source"] == "FireHOL")
        self.assertEqual(last["unknown"], "1")
        changes = list(study.csv_read(out / "comparisons/daily_comparisons.csv"))
        change = next(r for r in changes if r["current_date"] == "2026-09-17" and r["source"] == "FireHOL" and r["scope"] == "DK_ANY_MATCH")
        self.assertEqual((change["feed_added"], change["feed_removed"], change["registry_scope_left"]), ("1", "0", "1"))
        pairs = list(study.csv_read(out / "comparisons/all_date_pairs.csv"))
        self.assertTrue(any(r["calendar_gap_days"] == "3" for r in pairs))
        manifest = json.loads((out / "run_manifest.json").read_text())
        self.assertTrue(all(study.sha(out / p) == digest for p, digest in manifest["output_sha256"].items()))
        self.assertEqual(manifest["complete_dates"], 2)
        self.assertEqual(manifest["errors"], 0)
        self.assertIn("DK_PARTIAL", (out / "report.html").read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
