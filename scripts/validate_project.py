#!/usr/bin/env python3
"""Run a file-based quality checklist for the blocklist project."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAFE_ID = re.compile(r"[A-Za-z0-9_.-]+")


@dataclass
class Check:
    name: str
    status: str
    message: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def add(checks: list[Check], name: str, status: str, message: str) -> None:
    checks.append(Check(name=name, status=status, message=message))


def read_csv_file(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def resolve_logged_path(value: str) -> Path | None:
    """Resolve an old absolute path using its project-relative data/raw part."""

    if not value:
        return None
    direct = Path(value)
    if direct.exists():
        return direct
    marker = "data/raw/"
    if marker in value:
        return ROOT / "data" / "raw" / value.split(marker, 1)[1]
    return direct


def resolve_project_path(value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def check_project_files(checks: list[Check]) -> None:
    required = [
        "README.md",
        "CODE_STRUCTURE_README.md",
        "SUMMARY_AR.md",
        "STEPS.md",
        "MENU_GUIDE.md",
        "requirements.txt",
        "scripts/collect_snapshots.sh",
        "scripts/normalize_snapshot.py",
        "scripts/analyze_blocklists.py",
        "scripts/compare_snapshots.py",
        "scripts/run_daily_pipeline.py",
        "scripts/project_menu.py",
        "scripts/validate_project.py",
        "scripts/archive_project.py",
    ]
    missing = [item for item in required if not (ROOT / item).exists()]
    if missing:
        add(checks, "project files", "FAIL", "Missing: " + ", ".join(missing))
    else:
        add(checks, "project files", "PASS", f"All {len(required)} required project files are present.")


def check_syntax(checks: list[Check]) -> None:
    python_files = sorted((ROOT / "scripts").glob("*.py")) + sorted(ROOT.glob("*.py"))
    syntax_errors: list[str] = []
    for path in python_files:
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except (OSError, SyntaxError) as exc:
            syntax_errors.append(f"{relative_path(path)}: {exc}")
    if syntax_errors:
        add(checks, "Python syntax", "FAIL", " | ".join(syntax_errors[:3]))
    else:
        add(checks, "Python syntax", "PASS", f"Compiled {len(python_files)} Python files in memory.")

    shell_path = ROOT / "scripts/collect_snapshots.sh"
    result = subprocess.run(
        ["bash", "-n", str(shell_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        add(checks, "Bash syntax", "FAIL", result.stderr.strip() or "bash -n failed")
    else:
        add(checks, "Bash syntax", "PASS", "The collector passes bash -n.")

    tasks_path = ROOT / ".vscode/tasks.json"
    try:
        json.loads(tasks_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        add(checks, "VS Code tasks", "FAIL", str(exc))
    else:
        add(checks, "VS Code tasks", "PASS", ".vscode/tasks.json is valid JSON.")


def check_collection_log(checks: list[Check]) -> None:
    path = ROOT / "logs/collection_log.csv"
    expected = [
        "retrieved_at_utc",
        "source",
        "url",
        "http_status",
        "bytes",
        "sha256",
        "path",
        "status",
        "notes",
    ]
    if not path.exists():
        add(checks, "collection log", "WARN", "No collection log exists yet; run the daily pipeline first.")
        return
    try:
        fields, rows = read_csv_file(path)
    except (OSError, csv.Error) as exc:
        add(checks, "collection log", "FAIL", str(exc))
        return
    if fields != expected:
        add(checks, "collection log schema", "FAIL", f"Expected {expected}; found {fields}.")
        return
    bad: list[str] = []
    checked_files = 0
    for index, row in enumerate(rows, start=2):
        status = row.get("status", "")
        if status not in {"ok", "failed", "skipped"}:
            bad.append(f"line {index}: unknown status {status!r}")
            continue
        logged_path = resolve_logged_path(row.get("path", ""))
        if status == "ok" and logged_path is None:
            bad.append(f"line {index}: successful row has no file path")
            continue
        if logged_path is None or not logged_path.exists():
            if status == "ok":
                bad.append(f"line {index}: file does not exist: {row.get('path', '')}")
            continue
        checked_files += 1
        expected_bytes = row.get("bytes", "")
        if expected_bytes.isdigit() and int(expected_bytes) != logged_path.stat().st_size:
            bad.append(f"line {index}: byte count mismatch for {relative_path(logged_path)}")
        expected_hash = row.get("sha256", "")
        if expected_hash and expected_hash != sha256(logged_path):
            bad.append(f"line {index}: SHA-256 mismatch for {relative_path(logged_path)}")
    if bad:
        add(checks, "collection log integrity", "FAIL", " | ".join(bad[:4]))
    elif rows:
        add(checks, "collection log integrity", "PASS", f"Checked {len(rows)} rows and {checked_files} saved files.")
    else:
        add(checks, "collection log integrity", "WARN", "The collection log has a header but no rows.")


def check_normalized(checks: list[Check], run_id: str | None) -> list[str]:
    path = ROOT / "data/normalized/observations.csv"
    if not path.exists():
        add(
            checks,
            "normalized observations",
            "FAIL" if run_id else "WARN",
            "The normalized CSV does not exist.",
        )
        return []
    expected = {
        "snapshot_id",
        "source_name",
        "retrieved_at_utc",
        "source_path",
        "sha256",
        "indicator_type",
        "indicator",
    }
    try:
        fields, rows = read_csv_file(path)
    except (OSError, csv.Error) as exc:
        add(checks, "normalized observations", "FAIL", str(exc))
        return []
    missing = sorted(expected - set(fields))
    if missing:
        add(checks, "normalized schema", "FAIL", "Missing columns: " + ", ".join(missing))
        return []
    days: set[str] = set()
    bad_rows: list[str] = []
    for index, row in enumerate(rows, start=2):
        if not row.get("snapshot_id") or not row.get("source_name") or not row.get("indicator"):
            bad_rows.append(f"line {index}: missing identity field")
        stamp = row.get("retrieved_at_utc", "")
        day = stamp[:10]
        try:
            date.fromisoformat(day)
        except ValueError:
            bad_rows.append(f"line {index}: invalid retrieved_at_utc {stamp!r}")
        else:
            days.add(day)
        digest = row.get("sha256", "")
        if digest and not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            bad_rows.append(f"line {index}: invalid SHA-256")
    if bad_rows:
        add(checks, "normalized observations", "FAIL", " | ".join(bad_rows[:4]))
    elif rows:
        add(checks, "normalized observations", "PASS", f"Validated {len(rows)} rows with {len(days)} distinct UTC dates.")
    else:
        add(checks, "normalized observations", "WARN", "The normalized CSV has a valid header but no observations.")
    if len(days) >= 30:
        add(checks, "30-day coverage", "PASS", f"The study has {len(days)} distinct UTC dates.")
    else:
        add(checks, "30-day coverage", "WARN", f"Only {len(days)} distinct UTC date(s) are available; 30 are planned.")
    return sorted(days)


def check_results(checks: list[Check], run_id: str | None) -> None:
    required = [
        "daily_summary.csv",
        "persistence.csv",
        "overlap.csv",
        "analysis_notes.txt",
        "daily_unique_indicators.png",
        "daily_additions_removals.png",
        "source_overlap_heatmap.png",
    ]
    missing = [item for item in required if not (ROOT / "results" / item).exists()]
    if missing:
        add(
            checks,
            "analysis outputs",
            "FAIL" if run_id else "WARN",
            "Missing: " + ", ".join(missing),
        )
        return
    try:
        _, daily_rows = read_csv_file(ROOT / "results/daily_summary.csv")
    except (OSError, csv.Error) as exc:
        add(checks, "analysis outputs", "FAIL", str(exc))
        return
    add(checks, "analysis outputs", "PASS", f"All {len(required)} core outputs exist; daily summary has {len(daily_rows)} rows.")


def check_run_records(checks: list[Check], run_id: str | None) -> None:
    root = ROOT / "run_records"
    if not root.exists():
        add(checks, "run records", "WARN", "No run_records directory exists yet.")
        return
    directories = sorted(path for path in root.iterdir() if path.is_dir())
    if run_id:
        selected = [root / run_id]
    else:
        selected = directories
    if not selected or any(not path.exists() for path in selected):
        add(checks, "run records", "FAIL" if run_id else "WARN", "The requested run record does not exist.")
        return
    failures: list[str] = []
    warnings: list[str] = []
    checked = 0
    for directory in selected:
        checked += 1
        manifest_path = directory / "run_manifest.json"
        events_path = directory / "run_events.csv"
        summary_path = directory / "run_summary.md"
        collection_path = directory / "collection.csv"
        if not all(path.exists() for path in (manifest_path, events_path, collection_path)):
            message = f"{directory.name}: missing manifest, events or collection record"
            if run_id:
                failures.append(message)
            else:
                warnings.append(message)
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            fields, events = read_csv_file(events_path)
        except (OSError, json.JSONDecodeError, csv.Error) as exc:
            failures.append(f"{directory.name}: {exc}")
            continue
        current_run_is_still_running = directory.name == run_id and manifest.get("status") == "running"
        if not summary_path.exists() and not current_run_is_still_running:
            failures.append(f"{directory.name}: run_summary.md is missing")
        if manifest.get("run_id") != directory.name:
            failures.append(f"{directory.name}: manifest run_id does not match folder")
        if manifest.get("status") not in {"running", "succeeded", "failed"}:
            failures.append(f"{directory.name}: invalid manifest status")
        if fields != ["event_time_utc", "step", "event", "status", "details"] or not events:
            failures.append(f"{directory.name}: invalid or empty event log")
        analysis = manifest.get("analysis", {})
        archive_dir = directory / "analysis"
        if analysis.get("status") == "archived":
            for item in analysis.get("files", []):
                path = resolve_project_path(str(item.get("path", "")))
                if not path.exists() or (item.get("sha256") and sha256(path) != item["sha256"]):
                    failures.append(f"{directory.name}: archived analysis hash/path problem")
                    break
            if not archive_dir.exists():
                failures.append(f"{directory.name}: analysis archive is missing")
        comparison = manifest.get("comparison", {})
        if comparison.get("status") == "created":
            output_dir = resolve_project_path(str(comparison.get("output_dir", "")))
            if not output_dir.exists() or not (output_dir / "comparison_manifest.json").exists():
                failures.append(f"{directory.name}: comparison output is missing")
        elif comparison.get("status") == "not_ready":
            status_file = resolve_project_path(str(comparison.get("status_file", "")))
            if not status_file.exists():
                failures.append(f"{directory.name}: comparison status file is missing")
    if failures:
        add(checks, "run records", "FAIL", " | ".join(failures[:4]))
    elif warnings:
        add(checks, "run records", "WARN", " | ".join(warnings[:4]))
    else:
        add(checks, "run records", "PASS", f"Checked {checked} timestamped run record(s).")


def check_comparisons(checks: list[Check]) -> None:
    root = ROOT / "comparisons"
    if not root.exists():
        add(checks, "comparison archive", "WARN", "No comparisons exist yet; the first day is expected to be not_ready.")
        return
    failures: list[str] = []
    manifests = list(root.glob("**/comparison_manifest.json"))
    statuses = list(root.glob("status_*.json"))
    for path in statuses:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            failures.append(f"{relative_path(path)}: {exc}")
            continue
        if payload.get("status") not in {"not_ready", "error"}:
            failures.append(f"{relative_path(path)}: invalid status")
    for path in manifests:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            failures.append(f"{relative_path(path)}: {exc}")
            continue
        for item in payload.get("outputs", []):
            output = resolve_project_path(str(item.get("path", "")))
            if not output.exists() or (item.get("sha256") and sha256(output) != item["sha256"]):
                failures.append(f"{relative_path(path)}: output hash/path problem")
                break
    if failures:
        add(checks, "comparison archive", "FAIL", " | ".join(failures[:4]))
    elif manifests or statuses:
        add(checks, "comparison archive", "PASS", f"Checked {len(manifests)} comparison manifest(s) and {len(statuses)} status file(s).")
    else:
        add(checks, "comparison archive", "WARN", "The comparisons directory is empty.")


def check_report_files(checks: list[Check]) -> None:
    report_dir = ROOT / "report"
    if not report_dir.exists():
        add(checks, "report files", "WARN", "The report directory does not exist yet.")
        return
    files = sorted(report_dir.glob("*.docx"))
    if files:
        add(checks, "report files", "PASS", f"Found {len(files)} Word report/support file(s).")
    else:
        add(checks, "report files", "WARN", "No Word files are present yet.")


def validate(run_id: str | None) -> list[Check]:
    checks: list[Check] = []
    check_project_files(checks)
    check_syntax(checks)
    check_collection_log(checks)
    check_normalized(checks, run_id)
    check_results(checks, run_id)
    check_run_records(checks, run_id)
    check_comparisons(checks)
    check_report_files(checks)
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", help="Validate one particular run record.")
    parser.add_argument("--json-out", type=Path, help="Also save the checklist as a JSON report.")
    args = parser.parse_args()
    if args.run_id and not SAFE_ID.fullmatch(args.run_id):
        parser.error("--run-id may contain only letters, numbers, underscore, period and hyphen")

    checks = validate(args.run_id)
    failures = sum(item.status == "FAIL" for item in checks)
    warnings = sum(item.status == "WARN" for item in checks)
    passes = sum(item.status == "PASS" for item in checks)
    overall = "failed" if failures else "passed_with_warnings" if warnings else "passed"
    report = {
        "schema_version": 1,
        "validated_at_utc": utc_now(),
        "project": "Analysis of Public Blocklists from a Danish Perspective",
        "run_id": args.run_id or "",
        "status": overall,
        "summary": {"pass": passes, "warn": warnings, "fail": failures},
        "checks": [asdict(item) for item in checks],
        "rule": "Values are read from project files; unavailable data is reported as a warning or failure and is not invented.",
    }
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print("PROJECT VALIDATION CHECKLIST")
    print("=" * 29)
    for item in checks:
        print(f"[{item.status}] {item.name}: {item.message}")
    print("-" * 29)
    print(f"validation_status={overall}")
    print(f"validation_pass={passes}")
    print(f"validation_warn={warnings}")
    print(f"validation_fail={failures}")
    if args.json_out:
        print(f"validation_report={relative_path(args.json_out)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
