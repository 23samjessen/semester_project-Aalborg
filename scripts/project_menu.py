#!/usr/bin/env python3
"""Beginner-friendly menu for the public blocklist study."""

from __future__ import annotations

import csv
import json
import os
import shlex
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_day() -> str:
    return utc_now().date().isoformat()


def local_now() -> datetime:
    return datetime.now().astimezone()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def print_table(rows: list[dict[str, str]], columns: list[str], limit: int = 20) -> None:
    if not rows:
        print("No records are available for this selection.")
        return
    shown = rows[:limit]
    values = {
        column: [str(row.get(column, "")) for row in shown]
        for column in columns
    }
    widths = {
        column: min(32, max(len(column), *(len(value) for value in values[column])))
        for column in columns
    }

    def cell(column: str, value: str) -> str:
        text = value.replace("\n", " ")
        if len(text) > widths[column]:
            text = text[: widths[column] - 3] + "..."
        return text.ljust(widths[column])

    print(" | ".join(cell(column, column) for column in columns))
    print("-+-".join("-" * widths[column] for column in columns))
    for row in shown:
        print(" | ".join(cell(column, str(row.get(column, ""))) for column in columns))
    if len(rows) > limit:
        print(f"Showing {limit} of {len(rows)} records. Use the date-specific option for a smaller selection.")


def run_command(command: list[str]) -> int:
    print()
    print("Running:", shlex.join(command))
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr)
    print(f"Command exit code: {completed.returncode}")
    return completed.returncode


def run_id_from_output(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("run_id="):
            return line.split("=", 1)[1].strip()
    return ""


def run_pipeline(skip_collection: bool) -> None:
    if not skip_collection:
        if not os.environ.get("BLOCKLIST_USER_AGENT"):
            print("Set a group contact string before collecting public feeds:")
            print("export BLOCKLIST_USER_AGENT='AAU-blocklist-study/0.1 contact: GROUP-EMAIL'")
            print("No network request was made.")
            return
        print("This option downloads the enabled public feeds and saves the original responses.")
        print("It does not scan, connect to or test any IP address found in a feed.")
        if input("Type RUN to continue: ").strip() != "RUN":
            print("Collection cancelled; no network request was made.")
            return
    command = [sys.executable, "scripts/run_daily_pipeline.py"]
    if skip_collection:
        command.append("--skip-collection")
    run_command(command)


def latest_run_ids() -> list[str]:
    root = ROOT / "run_records"
    if not root.exists():
        return []
    records: list[tuple[str, str]] = []
    for directory in root.iterdir():
        if not directory.is_dir():
            continue
        manifest = directory / "run_manifest.json"
        started = ""
        if manifest.exists():
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                started = str(payload.get("started_at_utc", ""))
            except (OSError, ValueError):
                pass
        records.append((started, directory.name))
    return [name for _, name in sorted(records, reverse=True)]


def run_dates(run_id: str) -> list[str]:
    path = ROOT / "run_records" / run_id / "run_manifest.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [str(value) for value in payload.get("normalized", {}).get("distinct_snapshot_days", [])]


def show_run_summary(run_id: str) -> None:
    path = ROOT / "run_records" / run_id / "run_summary.md"
    if not path.exists():
        print(f"Run record not found: {run_id}")
        return
    print()
    print(path.read_text(encoding="utf-8").rstrip())


def available_days() -> list[str]:
    days: set[str] = set()
    for row in read_csv(ROOT / "data/normalized/observations.csv"):
        stamp = row.get("retrieved_at_utc", "")
        if len(stamp) >= 10:
            try:
                date.fromisoformat(stamp[:10])
            except ValueError:
                continue
            days.add(stamp[:10])
    return sorted(days)


def ask_date(prompt: str, default: str | None = None) -> str:
    while True:
        suffix = f" [{default}]" if default else ""
        value = input(f"{prompt}{suffix}: ").strip() or (default or "")
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            print("Use the date format YYYY-MM-DD.")


def collection_rows_for_day(day: str) -> list[dict[str, str]]:
    return [
        row
        for row in read_csv(ROOT / "logs/collection_log.csv")
        if row.get("retrieved_at_utc", "")[:10] == day
    ]


def show_day_logs(day: str) -> None:
    print(f"\nCollection records for UTC date {day}")
    rows = collection_rows_for_day(day)
    print_table(rows, ["retrieved_at_utc", "source", "http_status", "bytes", "status", "sha256", "path", "notes"])
    raw_dir = ROOT / "data/raw" / day
    print(f"\nRaw snapshot folder: {raw_dir}")
    if raw_dir.exists():
        raw_files = sorted(path.name for path in raw_dir.iterdir() if path.is_file())
        print("\n".join(raw_files) if raw_files else "The folder exists but contains no files.")
    else:
        print("The raw folder does not exist.")
    matching_runs = [run_id for run_id in latest_run_ids() if day in run_dates(run_id)]
    print(f"\nRun records containing {day}: {', '.join(matching_runs) if matching_runs else 'none'}")


def show_today_result() -> None:
    day = utc_day()
    print(f"UTC date used for the result: {day}")
    print(f"Mac local time shown for orientation: {local_now().isoformat()}")
    rows = [row for row in read_csv(ROOT / "results/daily_summary.csv") if row.get("snapshot_day") == day]
    print_table(
        rows,
        ["source", "snapshot_day", "unique_indicators", "unique_ips_cidrs", "unique_domains_urls", "additions", "removals", "raw_rows"],
    )
    if not rows:
        print("No result for the current UTC date is available. Available dates:", ", ".join(available_days()) or "none")
    runs = [run_id for run_id in latest_run_ids() if day in run_dates(run_id)]
    if runs:
        print(f"Newest run record for {day}: {runs[0]}")


def show_today_logs() -> None:
    show_day_logs(utc_day())


def validate_project() -> None:
    chosen = input("Run ID to validate, or press Enter for the whole project: ").strip()
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    report = ROOT / "logs/validation" / f"validation_{stamp}.json"
    command = [sys.executable, "scripts/validate_project.py", "--json-out", str(report)]
    if chosen:
        command.extend(["--run-id", chosen])
    run_command(command)
    print(f"Checklist report: {report}")


def compare_dates(previous_day: str, current_day: str) -> None:
    if previous_day >= current_day:
        print("The previous date must be earlier than the current date.")
        return
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    run_id = f"menu_compare_{stamp}"
    command = [
        sys.executable,
        "scripts/compare_snapshots.py",
        "--input",
        "data/normalized/observations.csv",
        "--out-dir",
        "comparisons",
        "--previous-day",
        previous_day,
        "--current-day",
        current_day,
        "--run-id",
        run_id,
    ]
    run_command(command)
    print(f"Comparison ID: {run_id}")


def compare_today_yesterday() -> None:
    today = utc_now().date()
    yesterday = today - timedelta(days=1)
    print(f"Comparing UTC dates: {yesterday.isoformat()} -> {today.isoformat()}")
    compare_dates(yesterday.isoformat(), today.isoformat())


def compare_two_dates() -> None:
    days = available_days()
    print("Available normalized UTC dates:", ", ".join(days) or "none")
    if len(days) < 2:
        print("At least two distinct dates are required. No comparison was made.")
        return
    previous = ask_date("Enter the earlier date")
    current = ask_date("Enter the later date")
    compare_dates(previous, current)


def show_archived_run() -> None:
    runs = latest_run_ids()
    if not runs:
        print("No run records exist yet.")
        return
    print("Available run records, newest first:")
    rows: list[dict[str, str]] = []
    for run_id in runs:
        manifest_path = ROOT / "run_records" / run_id / "run_manifest.json"
        status = "unknown"
        started = ""
        if manifest_path.exists():
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                status = str(payload.get("status", ""))
                started = str(payload.get("started_at_utc", ""))
            except (OSError, ValueError):
                pass
        rows.append({"run_id": run_id, "started_at_utc": started, "status": status})
    print_table(rows, ["run_id", "started_at_utc", "status"], limit=30)
    chosen = input("Enter a run ID, or press Enter for the newest: ").strip() or runs[0]
    show_run_summary(chosen)
    directory = ROOT / "run_records" / chosen
    if directory.exists():
        print("\nSaved files in this run record:")
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                print(path.relative_to(ROOT))


def create_backup() -> None:
    print("This creates a timestamped ZIP backup of code, reports, raw data, logs and run archives.")
    print("It excludes the virtual environment, caches, old ZIP files and the archives folder itself.")
    if input("Type BACKUP to continue: ").strip() != "BACKUP":
        print("Backup cancelled.")
        return
    run_command([sys.executable, "scripts/archive_project.py"])


def show_status() -> None:
    normalized = ROOT / "data/normalized/observations.csv"
    normalized_rows = read_csv(normalized)
    result_files = sorted(path.name for path in (ROOT / "results").glob("*") if path.is_file())
    run_count = len(latest_run_ids())
    comparison_count = len(list((ROOT / "comparisons").glob("**/comparison_manifest.json"))) if (ROOT / "comparisons").exists() else 0
    print("\nPROJECT STATUS")
    print(f"Mac local time: {local_now().isoformat()}")
    print(f"Canonical UTC time: {utc_now().isoformat().replace('+00:00', 'Z')}")
    print(f"Normalized rows: {len(normalized_rows)}")
    print(f"Distinct UTC dates: {len(available_days())} ({', '.join(available_days()) or 'none'})")
    print(f"Raw snapshot days: {len([p for p in (ROOT / 'data/raw').glob('*') if p.is_dir()]) if (ROOT / 'data/raw').exists() else 0}")
    print(f"Run records: {run_count}")
    print(f"Created comparison folders: {comparison_count}")
    print(f"Result files: {', '.join(result_files) or 'none'}")
    print("Storage rule: raw evidence is preserved; normalized data and results are reproducible; comparisons are separate.")


def print_menu() -> None:
    print("\n" + "=" * 72)
    print("PUBLIC BLOCKLIST STUDY — PROJECT MENU")
    print("=" * 72)
    print(f"Mac local time: {local_now().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Canonical project date (UTC): {utc_day()}")
    print("Choose a number. Only option 1 makes network requests.")
    print()
    items = [
        ("1", "Run complete daily pipeline", "download -> normalize -> analyze -> compare -> validate"),
        ("2", "Run again without downloading", "reuse saved raw files; useful for a safe replay"),
        ("3", "Display today's result", "show actual analysis rows for today's UTC date"),
        ("4", "Show today's collection log", "show URLs, status, timestamps, hashes and raw paths"),
        ("5", "Show logs for a chosen date", "inspect day 1, day 2 or any saved UTC date"),
        ("6", "Run validation checklist", "check files, syntax, hashes, outputs, archives and comparisons"),
        ("7", "Compare today with yesterday", "create a separate comparison folder; no results are overwritten"),
        ("8", "Compare two chosen dates", "select exact earlier and later UTC dates"),
        ("9", "Open an archived run record", "read the summary and list every saved file"),
        ("10", "Create a timestamped backup ZIP", "archive the whole project without including old ZIPs"),
        ("11", "Show project status", "display dates, row count, runs, comparisons and result files"),
        ("0", "Exit", "close the menu"),
    ]
    for number, title, explanation in items:
        print(f"{number:>2}. {title:<34} — {explanation}")


def main() -> int:
    while True:
        print_menu()
        choice = input("\nChoose an option: ").strip()
        if choice == "0":
            print("Menu closed. The saved files remain in the project folder.")
            return 0
        if choice == "1":
            run_pipeline(skip_collection=False)
        elif choice == "2":
            run_pipeline(skip_collection=True)
        elif choice == "3":
            show_today_result()
        elif choice == "4":
            show_today_logs()
        elif choice == "5":
            show_day_logs(ask_date("Enter the UTC date to inspect", utc_day()))
        elif choice == "6":
            validate_project()
        elif choice == "7":
            compare_today_yesterday()
        elif choice == "8":
            compare_two_dates()
        elif choice == "9":
            show_archived_run()
        elif choice == "10":
            create_backup()
        elif choice == "11":
            show_status()
        else:
            print("That option is not available. Choose a number from the menu.")
        input("\nPress Enter to return to the menu...")


if __name__ == "__main__":
    raise SystemExit(main())
