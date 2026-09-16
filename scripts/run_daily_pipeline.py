#!/usr/bin/env python3
"""Run the daily collection pipeline and archive a traceable run record."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "run"


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_skipped_collection_log(path: Path, event_time: str) -> None:
    """Leave an explicit per-run record when network collection is skipped."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
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
        )
        writer.writerow(
            [
                event_time,
                "pipeline",
                "",
                "not_requested",
                "0",
                "",
                "",
                "skipped",
                "--skip-collection was used; existing raw snapshots were reused and no network requests were made",
            ]
        )


def append_event(path: Path, event_time: str, step: str, event: str, status: str, details: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if new_file:
            writer.writerow(["event_time_utc", "step", "event", "status", "details"])
        writer.writerow([event_time, step, event, status, details])


def normalized_metadata(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"path": relative_path(path), "status": "missing"}
    with path.open(newline="", encoding="utf-8") as handle:
        row_count = max(sum(1 for _ in handle) - 1, 0)
    days: set[str] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            value = (row.get("retrieved_at_utc") or "")[:10]
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                days.add(value)
    return {
        "path": relative_path(path),
        "status": "present",
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "row_count": row_count,
        "distinct_snapshot_days": sorted(days),
    }


def archive_analysis(results_dir: Path, archive_dir: Path) -> list[dict[str, str]]:
    archive_dir.mkdir(parents=True, exist_ok=True)
    archived: list[dict[str, str]] = []
    if not results_dir.exists():
        return archived
    for source_path in sorted(results_dir.iterdir()):
        if not source_path.is_file():
            continue
        destination = archive_dir / source_path.name
        shutil.copy2(source_path, destination)
        archived.append({"path": relative_path(destination), "sha256": sha256(destination)})
    return archived


def command_display(command: list[str]) -> str:
    displayed: list[str] = []
    for item in command:
        try:
            displayed.append(str(Path(item).resolve().relative_to(ROOT.resolve())))
        except (ValueError, OSError):
            displayed.append(item)
    return " ".join(displayed)


def run_command(
    step: str,
    command: list[str],
    environment: dict[str, str],
    run_dir: Path,
    events_path: Path,
    manifest: dict[str, object],
) -> tuple[int, str, str]:
    started_at = utc_now()
    append_event(
        events_path,
        started_at,
        step,
        "command_started",
        "running",
        command_display(command),
    )
    index = len(manifest["steps"]) + 1
    stdout_path = run_dir / f"step_{index:02d}_{step}.stdout.log"
    stderr_path = run_dir / f"step_{index:02d}_{step}.stderr.log"
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    finished_at = utc_now()
    status = "succeeded" if completed.returncode == 0 else "failed"
    detail = f"exit_code={completed.returncode}; stdout={relative_path(stdout_path)}; stderr={relative_path(stderr_path)}"
    append_event(events_path, finished_at, step, "command_finished", status, detail)
    manifest["steps"].append(
        {
            "step": step,
            "command": command_display(command),
            "started_at_utc": started_at,
            "finished_at_utc": finished_at,
            "status": status,
            "exit_code": completed.returncode,
            "stdout_log": relative_path(stdout_path),
            "stderr_log": relative_path(stderr_path),
        }
    )
    return completed.returncode, completed.stdout, completed.stderr


def write_run_summary(path: Path, manifest: dict[str, object]) -> None:
    collection = manifest.get("collection", {})
    normalized = manifest.get("normalized", {})
    comparison = manifest.get("comparison", {})
    analysis = manifest.get("analysis", {})
    validation = manifest.get("validation", {})
    comparison_output = comparison.get("output_dir") or comparison.get("status_file", "")
    lines = [
        "# Daily pipeline run record",
        "",
        f"Run ID: {manifest['run_id']}",
        f"Started at UTC: {manifest['started_at_utc']}",
        f"Finished at UTC: {manifest.get('finished_at_utc', '')}",
        f"Overall status: {manifest.get('status', '')}",
        "",
        "## Collection",
        "",
        f"Status: {collection.get('status', '')}",
        f"Per-run collection log: {collection.get('per_run_log', '')}",
        "",
        "## Normalization",
        "",
        f"File: {normalized.get('path', '')}",
        f"Rows: {normalized.get('row_count', '')}",
        f"SHA-256: {normalized.get('sha256', '')}",
        f"Distinct dates available: {', '.join(normalized.get('distinct_snapshot_days', []))}",
        "",
        "## Analysis",
        "",
        f"Archived analysis directory: {analysis.get('archive_dir', '')}",
        f"Archived files: {len(analysis.get('files', []))}",
        "",
        "## Comparison",
        "",
        f"Status: {comparison.get('status', '')}",
        f"Output: {comparison_output}",
        "",
        "## Validation checklist",
        "",
        f"Status: {validation.get('status', '')}",
        f"Report: {validation.get('report', '')}",
        f"Pass/Warn/Fail: {validation.get('pass', '')}/{validation.get('warn', '')}/{validation.get('fail', '')}",
        "",
        "Use run_manifest.json, run_events.csv and the command stdout/stderr logs for the complete audit trail.",
        "The comparison output is separate from results/ and does not overwrite cumulative analysis.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_comparison_output(stdout: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.startswith("comparison_"):
            values[key] = value.strip()
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-collection",
        action="store_true",
        help="Reuse existing raw snapshots; useful for rerunning analysis after a parser change.",
    )
    parser.add_argument("--run-id", help="Optional safe run ID, mainly for controlled tests.")
    args = parser.parse_args()

    generated_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = args.run_id or f"{generated_stamp}_run_{uuid.uuid4().hex[:8]}"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", run_id):
        parser.error("--run-id may contain only letters, numbers, underscore, period and hyphen")

    run_dir = ROOT / "run_records" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "run_events.csv"
    manifest: dict[str, object] = {
        "schema_version": 1,
        "project": "Analysis of Public Blocklists from a Danish Perspective",
        "run_id": run_id,
        "started_at_utc": utc_now(),
        "finished_at_utc": "",
        "status": "running",
        "timezone": "UTC",
        "entrypoint": "scripts/run_daily_pipeline.py",
        "collection": {
            "status": "skipped" if args.skip_collection else "pending",
            "per_run_log": relative_path(run_dir / "collection.csv"),
        },
        "steps": [],
        "normalized": {},
        "analysis": {},
        "comparison": {},
        "validation": {},
        "safety": {
            "raw_snapshots_are_immutable": True,
            "comparison_directory_is_separate": True,
            "api_keys_written_to_manifest": False,
        },
    }
    manifest_path = run_dir / "run_manifest.json"
    write_json(manifest_path, manifest)
    append_event(
        events_path,
        manifest["started_at_utc"],
        "pipeline",
        "pipeline_started",
        "running",
        f"run_id={run_id}",
    )
    if args.skip_collection:
        write_skipped_collection_log(run_dir / "collection.csv", manifest["started_at_utc"])
        append_event(
            events_path,
            utc_now(),
            "collect",
            "collection_skipped",
            "skipped",
            "--skip-collection was used; no network requests were made",
        )

    environment = os.environ.copy()
    environment["BLOCKLIST_RUN_ID"] = run_id
    python = sys.executable
    commands: list[tuple[str, list[str]]] = []
    if not args.skip_collection:
        commands.append(("collect", ["bash", "scripts/collect_snapshots.sh"]))
    commands.extend(
        [
            (
                "normalize",
                [
                    python,
                    "scripts/normalize_snapshot.py",
                    "--raw-dir",
                    "data/raw",
                    "--out",
                    "data/normalized/observations.csv",
                    "--errors",
                    "logs/normalization_errors.csv",
                ],
            ),
            (
                "analyze",
                [
                    python,
                    "scripts/analyze_blocklists.py",
                    "--input",
                    "data/normalized/observations.csv",
                    "--out-dir",
                    "results",
                ],
            ),
        ]
    )

    exit_code = 0
    try:
        for step, command in commands:
            step_code, stdout, _stderr = run_command(
                step,
                command,
                environment,
                run_dir,
                events_path,
                manifest,
            )
            if step == "collect":
                manifest["collection"]["status"] = "succeeded" if step_code == 0 else "failed"
            if step_code != 0:
                exit_code = step_code
                manifest["status"] = "failed"
                manifest["failure_step"] = step
                break
            if step == "collect":
                manifest["collection"]["completed_at_utc"] = manifest["steps"][-1]["finished_at_utc"]

        normalized_path = ROOT / "data/normalized/observations.csv"
        manifest["normalized"] = normalized_metadata(normalized_path)
        parser_errors = ROOT / "logs/normalization_errors.csv"
        if parser_errors.exists():
            errors_copy = run_dir / "normalization_errors.csv"
            shutil.copy2(parser_errors, errors_copy)
            manifest["normalized"]["errors_file"] = relative_path(errors_copy)
            manifest["normalized"]["errors_sha256"] = sha256(errors_copy)
            append_event(
                events_path,
                utc_now(),
                "normalize",
                "parser_errors_archived",
                "succeeded",
                f"path={relative_path(errors_copy)}",
            )
        if exit_code == 0 and manifest["normalized"].get("status") == "present":
            archive_dir = run_dir / "analysis"
            archived_files = archive_analysis(ROOT / "results", archive_dir)
            manifest["analysis"] = {
                "status": "archived",
                "scope": "cumulative normalized observations available at the end of this run",
                "source_dir": "results",
                "archive_dir": relative_path(archive_dir),
                "files": archived_files,
                "archived_at_utc": utc_now(),
            }
            append_event(
                events_path,
                manifest["analysis"]["archived_at_utc"],
                "archive_analysis",
                "analysis_archived",
                "succeeded",
                f"files={len(archived_files)}; destination={relative_path(archive_dir)}",
            )

            compare_command = [
                python,
                "scripts/compare_snapshots.py",
                "--input",
                "data/normalized/observations.csv",
                "--out-dir",
                "comparisons",
                "--run-id",
                run_id,
            ]
            compare_code, compare_stdout, compare_stderr = run_command(
                "compare",
                compare_command,
                environment,
                run_dir,
                events_path,
                manifest,
            )
            compare_values = parse_comparison_output(compare_stdout)
            comparison_status = compare_values.get("comparison_status", "error")
            manifest["comparison"] = {
                "status": comparison_status,
                "previous_day": compare_values.get("comparison_previous_day", ""),
                "current_day": compare_values.get("comparison_current_day", ""),
                "changed_rows": compare_values.get("comparison_changed_rows", ""),
                "output_dir": compare_values.get("comparison_dir", ""),
                "status_file": compare_values.get("comparison_status_file", ""),
                "stderr_present": bool(compare_stderr.strip()),
                "completed_at_utc": utc_now(),
            }
            if compare_code != 0:
                exit_code = compare_code
                manifest["status"] = "failed"
                manifest["failure_step"] = "compare"
            append_event(
                events_path,
                manifest["comparison"]["completed_at_utc"],
                "compare",
                "comparison_recorded",
                comparison_status,
                json.dumps(manifest["comparison"], ensure_ascii=True),
            )
            validation_report = run_dir / "validation_report.json"
            validation_command = [
                python,
                "scripts/validate_project.py",
                "--run-id",
                run_id,
                "--json-out",
                relative_path(validation_report),
            ]
            validation_code, validation_stdout, validation_stderr = run_command(
                "validate",
                validation_command,
                environment,
                run_dir,
                events_path,
                manifest,
            )
            validation_values: dict[str, str] = {}
            for line in validation_stdout.splitlines():
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.startswith("validation_"):
                    validation_values[key] = value.strip()
            manifest["validation"] = {
                "status": validation_values.get("validation_status", "error"),
                "report": validation_values.get("validation_report", relative_path(validation_report)),
                "pass": validation_values.get("validation_pass", ""),
                "warn": validation_values.get("validation_warn", ""),
                "fail": validation_values.get("validation_fail", ""),
                "stderr_present": bool(validation_stderr.strip()),
                "completed_at_utc": utc_now(),
            }
            if validation_report.exists():
                manifest["validation"]["report_bytes"] = validation_report.stat().st_size
                manifest["validation"]["report_sha256"] = sha256(validation_report)
            if validation_code != 0:
                exit_code = validation_code
                manifest["status"] = "failed"
                manifest["failure_step"] = "validate"
            append_event(
                events_path,
                manifest["validation"]["completed_at_utc"],
                "validate",
                "validation_recorded",
                manifest["validation"]["status"],
                json.dumps(manifest["validation"], ensure_ascii=True),
            )
        elif exit_code == 0:
            exit_code = 1
            manifest["status"] = "failed"
            manifest["failure_step"] = "normalized_data"
    except Exception as exc:
        exit_code = 1
        manifest["status"] = "failed"
        manifest["failure_step"] = "runner"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        append_event(events_path, utc_now(), "runner", "exception", "failed", manifest["error"])
    finally:
        if exit_code == 0:
            manifest["status"] = "succeeded"
        manifest["finished_at_utc"] = utc_now()
        append_event(
            events_path,
            manifest["finished_at_utc"],
            "pipeline",
            "pipeline_finished",
            manifest["status"],
            f"run_id={run_id}",
        )
        write_json(manifest_path, manifest)
        write_run_summary(run_dir / "run_summary.md", manifest)

    print(f"run_status={manifest['status']}")
    print(f"run_id={run_id}")
    print(f"run_record_dir={relative_path(run_dir)}")
    print(f"run_manifest={relative_path(manifest_path)}")
    if manifest.get("comparison", {}).get("status"):
        print(f"comparison_status={manifest['comparison']['status']}")
    if manifest.get("validation", {}).get("status"):
        print(f"validation_status={manifest['validation']['status']}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
