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
        print(
            f"Showing {limit} of {len(rows)} records. "
            "Use the date-specific option for a smaller selection."
        )


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


def run_pipeline(skip_collection: bool) -> None:
    if not skip_collection:
        if not os.environ.get("BLOCKLIST_USER_AGENT"):
            print("Set a group contact string before collecting public feeds:")
            print(
                "export BLOCKLIST_USER_AGENT="
                "'AAU-blocklist-study/0.1 contact: GROUP-EMAIL'"
            )
            print("No network request was made.")
            return

        print(
            "This option downloads the enabled public feeds and saves "
            "the original responses."
        )
        print(
            "It does not scan, connect to or test any IP address found in a feed."
        )
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


def clean_run_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for run_id in latest_run_ids():
        if "_run_" not in run_id:
            continue

        run_date = "unknown"
        run_time = "unknown"
        timestamp = run_id.split("_run_", 1)[0]

        try:
            parsed = datetime.strptime(timestamp, "%Y%m%dT%H%M%SZ")
            run_date = parsed.strftime("%Y-%m-%d")
            run_time = parsed.strftime("%H:%M:%S UTC")
        except ValueError:
            pass

        status = "unknown"
        collection_status = "unknown"
        manifest_path = ROOT / "run_records" / run_id / "run_manifest.json"

        if manifest_path.exists():
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                status = str(payload.get("status", "unknown"))
                collection = payload.get("collection", {})
                if isinstance(collection, dict):
                    collection_status = str(collection.get("status", "unknown"))
            except (OSError, ValueError):
                pass

        if collection_status == "succeeded":
            kind = "daily collection"
        elif collection_status == "skipped":
            kind = "replay"
        elif collection_status == "failed":
            kind = "collection failed"
        else:
            kind = "pipeline run"

        rows.append(
            {
                "number": str(len(rows) + 1),
                "date": run_date,
                "time_utc": run_time,
                "kind": kind,
                "status": status,
                "run_id": run_id,
            }
        )

    return rows


def run_dates(run_id: str) -> list[str]:
    path = ROOT / "run_records" / run_id / "run_manifest.json"
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []

    return [
        str(value)
        for value in payload.get("normalized", {}).get("distinct_snapshot_days", [])
    ]


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
    print_table(
        rows,
        [
            "retrieved_at_utc",
            "source",
            "http_status",
            "bytes",
            "status",
            "sha256",
            "path",
            "notes",
        ],
    )

    raw_dir = ROOT / "data/raw" / day
    print(f"\nRaw snapshot folder: {raw_dir}")
    if raw_dir.exists():
        raw_files = sorted(path.name for path in raw_dir.iterdir() if path.is_file())
        print("\n".join(raw_files) if raw_files else "The folder contains no files.")
    else:
        print("The raw folder does not exist.")

    matching_runs = [
        run_id for run_id in latest_run_ids() if day in run_dates(run_id)
    ]
    print(
        f"\nRun records containing {day}: "
        f"{', '.join(matching_runs) if matching_runs else 'none'}"
    )


def show_today_result() -> None:
    day = utc_day()
    print(f"UTC date used for the result: {day}")
    print(f"Mac local time shown for orientation: {local_now().isoformat()}")

    rows = [
        row
        for row in read_csv(ROOT / "results/daily_summary.csv")
        if row.get("snapshot_day") == day
    ]
    print_table(
        rows,
        [
            "source",
            "snapshot_day",
            "unique_indicators",
            "unique_ips_cidrs",
            "unique_domains_urls",
            "additions",
            "removals",
            "raw_rows",
        ],
    )

    if not rows:
        print(
            "No result for the current UTC date is available. Available dates: "
            + (", ".join(available_days()) or "none")
        )

    runs = [run_id for run_id in latest_run_ids() if day in run_dates(run_id)]
    if runs:
        print(f"Newest run record for {day}: {runs[0]}")


def show_today_logs() -> None:
    show_day_logs(utc_day())


def validate_project() -> None:
    rows = clean_run_rows()

    print()
    print("Available pipeline runs, newest first:")
    print_table(
        rows,
        ["number", "date", "time_utc", "kind", "status", "run_id"],
        limit=30,
    )

    chosen = input(
        "\nChoose a run number or paste a run ID; "
        "press Enter to validate the whole project: "
    ).strip()

    selected_run_id = ""

    if chosen:
        if chosen.isdigit():
            index = int(chosen) - 1
            if index < 0 or index >= len(rows):
                print("That run number is unavailable. Validation was not started.")
                return
            selected_run_id = rows[index]["run_id"]
        else:
            available_ids = {row["run_id"] for row in rows}
            if chosen not in available_ids:
                print("That run ID is not in the available pipeline-run list.")
                print("Use a displayed number, paste a displayed ID, or press Enter.")
                return
            selected_run_id = chosen

    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    report = ROOT / "logs/validation" / f"validation_{stamp}.json"
    command = [
        sys.executable,
        "scripts/validate_project.py",
        "--json-out",
        str(report),
    ]

    if selected_run_id:
        command.extend(["--run-id", selected_run_id])

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



def comparison_rows() -> list[dict[str, str]]:
    comparisons_root = ROOT / "comparisons"

    if not comparisons_root.exists():
        return []

    rows: list[dict[str, str]] = []

    for manifest_path in comparisons_root.glob(
        "*/*/comparison_manifest.json"
    ):
        try:
            payload = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            continue

        rows.append(
            {
                "generated_at_utc": str(
                    payload.get("generated_at_utc", "")
                ),
                "previous_day": str(
                    payload.get("previous_day", "")
                ),
                "current_day": str(
                    payload.get("current_day", "")
                ),
                "changed_rows": str(
                    payload.get("changed_indicator_rows", "")
                ),
                "status": str(
                    payload.get("status", "unknown")
                ),
                "comparison_id": str(
                    payload.get(
                        "run_id",
                        manifest_path.parents[1].name,
                    )
                ),
                "folder": str(
                    manifest_path.parent.relative_to(ROOT)
                ),
            }
        )

    rows.sort(
        key=lambda row: row["generated_at_utc"],
        reverse=True,
    )

    for number, row in enumerate(rows, start=1):
        row["number"] = str(number)

    return rows


def inspect_comparison() -> None:
    rows = comparison_rows()

    if not rows:
        print("No completed comparison results are available.")
        return

    print("\nAVAILABLE COMPARISONS — NEWEST FIRST")
    print_table(
        rows,
        [
            "number",
            "previous_day",
            "current_day",
            "changed_rows",
            "status",
            "comparison_id",
        ],
        limit=30,
    )

    chosen = input(
        "\nChoose a comparison number, "
        "or press Enter for the newest: "
    ).strip()

    if not chosen:
        selected = rows[0]
    elif chosen.isdigit() and 1 <= int(chosen) <= len(rows):
        selected = rows[int(chosen) - 1]
    else:
        print("That comparison number is unavailable.")
        return

    comparison_dir = ROOT / selected["folder"]
    summary_path = comparison_dir / "source_summary.csv"
    notes_path = comparison_dir / "comparison_notes.txt"

    print("\nCOMPARISON RESULT")
    print(f"Comparison ID: {selected['comparison_id']}")
    print(
        f"Compared dates: "
        f"{selected['previous_day']} -> "
        f"{selected['current_day']}"
    )
    print(
        f"Changed indicator rows: "
        f"{selected['changed_rows']}"
    )
    print(f"Result folder: {comparison_dir}")

    print("\nSUMMARY BY SOURCE AND INDICATOR TYPE")
    print_table(
        read_csv(summary_path),
        [
            "source",
            "indicator_type",
            "previous_count",
            "current_count",
            "added_count",
            "removed_count",
            "unchanged_count",
            "net_change",
            "percent_change",
            "comparison_status",
        ],
        limit=30,
    )

    print("\nHOW TO READ THE RESULT")
    print(
        "previous_count: unique indicators in the earlier snapshot."
    )
    print(
        "current_count: unique indicators in the later snapshot."
    )
    print(
        "added_count: present later but not present earlier."
    )
    print(
        "removed_count: present earlier but not present later."
    )
    print(
        "unchanged_count: present on both selected dates."
    )
    print(
        "net_change: current_count minus previous_count."
    )
    print(
        "percent_change: net change relative to previous_count."
    )
    print(
        "NA: a required source snapshot was missing; "
        "do not interpret it as a removal."
    )
    print(
        "A blocklist entry is not proof that an indicator "
        "is currently malicious."
    )

    print("\nFILES AND LOCATIONS")

    files = [
        (
            "source_summary.csv",
            "main statistical comparison",
        ),
        (
            "indicator_changes.csv",
            "all individual additions and removals",
        ),
        (
            "snapshot_index.csv",
            "input snapshots, timestamps and hashes",
        ),
        (
            "changes_by_source.png",
            "visual comparison chart",
        ),
        (
            "comparison_notes.txt",
            "method and limitations",
        ),
        (
            "comparison_manifest.json",
            "comparison identity and integrity record",
        ),
    ]

    for filename, purpose in files:
        file_path = comparison_dir / filename
        existence = "FOUND" if file_path.exists() else "MISSING"
        print(f"[{existence}] {file_path}")
        print(f"          Purpose: {purpose}")

    source_files = sorted(
        comparison_dir.glob("*_changes.csv")
    )

    if source_files:
        print("\nSOURCE-SPECIFIC CHANGE FILES")
        for source_file in source_files:
            if source_file.name != "indicator_changes.csv":
                print(source_file)

    if notes_path.exists():
        print("\nCOMPARISON METHOD NOTES")
        print(notes_path.read_text(encoding="utf-8").rstrip())

    print("\nRECOMMENDED ANALYSIS")
    print(
        "1. Compare additions and removals for each provider."
    )
    print(
        "2. Check whether most indicators remain unchanged."
    )
    print(
        "3. Identify providers with unusually high turnover."
    )
    print(
        "4. Check comparison_status and missing snapshots."
    )
    print(
        "5. Use repeated dates to study persistence over time."
    )
    print(
        "6. Analyse Danish relevance separately using evidence."
    )

def show_archived_run() -> None:
    rows = clean_run_rows()
    if not rows:
        print("No pipeline run records exist yet.")
        return

    print("Available pipeline runs, newest first:")
    print_table(
        rows,
        ["number", "date", "time_utc", "kind", "status", "run_id"],
        limit=30,
    )

    chosen = input("Choose a run number, or press Enter for the newest: ").strip()
    if not chosen:
        selected_run_id = rows[0]["run_id"]
    elif chosen.isdigit() and 1 <= int(chosen) <= len(rows):
        selected_run_id = rows[int(chosen) - 1]["run_id"]
    else:
        available_ids = {row["run_id"] for row in rows}
        if chosen not in available_ids:
            print("That run number or run ID is unavailable.")
            return
        selected_run_id = chosen

    show_run_summary(selected_run_id)
    directory = ROOT / "run_records" / selected_run_id
    if directory.exists():
        print("\nSaved files in this run record:")
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                print(path.relative_to(ROOT))


def create_backup() -> None:
    print(
        "This creates a timestamped ZIP backup of code, reports, raw data, "
        "logs and run archives."
    )
    print(
        "It excludes the virtual environment, caches, old ZIP files and "
        "the archives folder itself."
    )
    if input("Type BACKUP to continue: ").strip() != "BACKUP":
        print("Backup cancelled.")
        return
    run_command([sys.executable, "scripts/archive_project.py"])


def show_status() -> None:
    normalized_rows = read_csv(ROOT / "data/normalized/observations.csv")
    results_dir = ROOT / "results"
    result_files = (
        sorted(path.name for path in results_dir.glob("*") if path.is_file())
        if results_dir.exists()
        else []
    )
    raw_dir = ROOT / "data/raw"
    raw_days = (
        len([path for path in raw_dir.glob("*") if path.is_dir()])
        if raw_dir.exists()
        else 0
    )
    comparisons_dir = ROOT / "comparisons"
    comparison_count = (
        len(list(comparisons_dir.glob("**/comparison_manifest.json")))
        if comparisons_dir.exists()
        else 0
    )
    days = available_days()

    print("\nPROJECT STATUS")
    print(f"Mac local time: {local_now().isoformat()}")
    print(f"Canonical UTC time: {utc_now().isoformat().replace('+00:00', 'Z')}")
    print(f"Normalized rows: {len(normalized_rows)}")
    print(f"Distinct UTC dates: {len(days)} ({', '.join(days) or 'none'})")
    print(f"Raw snapshot days: {raw_days}")
    print(f"Pipeline run records: {len(clean_run_rows())}")
    print(f"Created comparison folders: {comparison_count}")
    print(f"Result files: {', '.join(result_files) or 'none'}")
    print(
        "Storage rule: raw evidence is preserved; normalized data and results "
        "are reproducible; comparisons are separate."
    )



def generate_final_study_package() -> None:
    days = available_days()
    available_count = len(days)
    required_count = 30

    print("\nFINAL STUDY EVIDENCE PACKAGE")
    print(f"Available distinct UTC dates: {available_count}")
    print(f"Required distinct UTC dates: {required_count}")

    command = [
        sys.executable,
        "scripts/generate_final_results.py",
    ]

    if available_count < required_count:
        remaining = required_count - available_count

        print(
            f"The final dataset is not ready. "
            f"{remaining} additional distinct date(s) "
            f"are required."
        )
        print(
            "A preview will be labelled PREVIEW — NOT FINAL."
        )

        confirmation = input(
            "Type PREVIEW to create a preliminary "
            "evidence package, or press Enter to cancel: "
        ).strip()

        if confirmation != "PREVIEW":
            print("Preview generation cancelled.")
            return

        command.append("--allow-preview")

    else:
        print(
            "The minimum 30-day coverage requirement "
            "has been reached."
        )
        print(
            "This creates a new timestamped package and "
            "does not overwrite previous evidence."
        )

        confirmation = input(
            "Type FINAL to generate the final evidence "
            "package, or press Enter to cancel: "
        ).strip()

        if confirmation != "FINAL":
            print("Final package generation cancelled.")
            return

    exit_code = run_command(command)

    if exit_code != 0:
        print(
            "The package was not created successfully. "
            "Review the output above."
        )
        return

    final_root = ROOT / "final_results"

    packages = sorted(
        [
            directory
            for directory in final_root.iterdir()
            if directory.is_dir()
        ],
        key=lambda directory: directory.name,
        reverse=True,
    ) if final_root.exists() else []

    if not packages:
        print(
            "No final-results package folder was found."
        )
        return

    newest = packages[0]

    print("\nPACKAGE CREATED SUCCESSFULLY")
    print(f"Package folder: {newest}")
    print(
        f"Main summary: "
        f"{newest / 'FINAL_STUDY_SUMMARY.md'}"
    )
    print(
        f"Quality report: "
        f"{newest / 'data_quality_report.csv'}"
    )
    print(
        f"Source statistics: "
        f"{newest / 'source_statistics.csv'}"
    )
    print(
        f"Comparison coverage: "
        f"{newest / 'comparison_coverage.csv'}"
    )
    print(
        f"Evidence index: "
        f"{newest / 'evidence_index.csv'}"
    )
    print(
        f"Manifest: "
        f"{newest / 'final_manifest.json'}"
    )
    print(
        "Theoretical policy, listing-reason and "
        "delisting conclusions still require cited "
        "manual research."
    )

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
        ("5", "Show logs for a chosen date", "inspect any saved UTC date"),
        ("6", "Run validation checklist", "check files, hashes, outputs, archives and comparisons"),
        ("7", "Compare today with yesterday", "save comparison separately; overwrite nothing"),
        ("8", "Compare two chosen dates", "select exact earlier and later UTC dates"),
        ("9", "Open an archived run record", "read a summary and list its saved files"),
        ("10", "Create a timestamped backup ZIP", "archive the project without old ZIPs"),
        ("11", "Show project status", "display dates, row count, runs and results"),
        (
            "12",
            "Inspect comparison results",
            "show dates, statistics, files and interpretation",
        ),
        (
            "100",
            "Generate final study package",
            "create a checked preview or final evidence package",
        ),
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
        elif choice == "12":
            inspect_comparison()
        elif choice == "100":
            generate_final_study_package()
        else:
            print("That option is unavailable. Choose a number from the menu.")

        input("\nPress Enter to return to the menu...")


if __name__ == "__main__":
    raise SystemExit(main())
