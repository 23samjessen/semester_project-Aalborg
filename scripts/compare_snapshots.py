#!/usr/bin/env python3
"""Compare the latest two distinct snapshot days without changing results/."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import date, datetime, timezone
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


def source_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "source"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def snapshot_day(row: dict[str, str]) -> str:
    value = row.get("retrieved_at_utc", "")
    candidate = value[:10]
    try:
        date.fromisoformat(candidate)
    except ValueError:
        return ""
    return candidate


def indicator_key(row: dict[str, str]) -> tuple[str, str] | None:
    indicator_type = (row.get("indicator_type") or "").strip()
    indicator = (row.get("indicator") or "").strip()
    if not indicator_type or not indicator:
        return None
    return indicator_type, indicator


def latest_snapshot(rows: list[dict[str, str]], source: str, day: str) -> dict[str, object] | None:
    """Select one latest successful snapshot for a source/day.

    More than one run may occur on a calendar day. Selecting the latest
    snapshot prevents a repeated same-day run from being counted as a new
    collection day and makes the two input states explicit in the manifest.
    """

    by_snapshot: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("source_name", "") != source or snapshot_day(row) != day:
            continue
        snapshot_id = row.get("snapshot_id") or row.get("source_path") or "unknown"
        by_snapshot[snapshot_id].append(row)
    if not by_snapshot:
        return None

    def snapshot_sort(item: tuple[str, list[dict[str, str]]]) -> tuple[str, str]:
        snapshot_id, entries = item
        latest_time = max((entry.get("retrieved_at_utc", "") for entry in entries), default="")
        return latest_time, snapshot_id

    snapshot_id, entries = max(by_snapshot.items(), key=snapshot_sort)
    indicators: dict[tuple[str, str], dict[str, str]] = {}
    for entry in entries:
        key = indicator_key(entry)
        if key is not None:
            existing = indicators.get(key)
            if existing is None or (
                entry.get("retrieved_at_utc", ""), entry.get("source_path", "")
            ) > (
                existing.get("retrieved_at_utc", ""), existing.get("source_path", "")
            ):
                indicators[key] = entry

    representative = max(
        entries,
        key=lambda entry: (entry.get("retrieved_at_utc", ""), entry.get("source_path", "")),
    )
    return {
        "source": source,
        "day": day,
        "snapshot_id": snapshot_id,
        "retrieved_at_utc": representative.get("retrieved_at_utc", ""),
        "source_path": representative.get("source_path", ""),
        "sha256": representative.get("sha256", ""),
        "indicators": indicators,
    }


def make_status(
    output_root: Path,
    run_id: str,
    input_path: Path,
    status: str,
    available_days: list[str],
    reason: str,
) -> Path:
    status_path = output_root / f"status_{safe_name(run_id)}.json"
    write_json(
        status_path,
        {
            "schema_version": 1,
            "status": status,
            "generated_at_utc": utc_now(),
            "run_id": run_id,
            "input_file": relative_path(input_path),
            "available_snapshot_days": available_days,
            "reason": reason,
            "results_directory_untouched": True,
        },
    )
    return status_path


def make_figure(summary: list[dict[str, object]], output_path: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    if not summary:
        return

    by_source: dict[str, dict[str, int]] = defaultdict(lambda: {"added": 0, "removed": 0})
    for row in summary:
        source = str(row["source"])
        try:
            added_count = int(row["added_count"])
            removed_count = int(row["removed_count"])
        except (TypeError, ValueError):
            # A missing source snapshot is represented by NA, not by a false
            # removal or addition. It must not break the comparison figure.
            continue
        by_source[source]["added"] += added_count
        by_source[source]["removed"] += removed_count

    sources = sorted(by_source)
    positions = list(range(len(sources)))
    width = 0.36
    fig, axis = plt.subplots(figsize=(9.5, max(4.2, len(sources) * 0.75)))
    axis.barh(
        [position + width / 2 for position in positions],
        [by_source[source]["added"] for source in sources],
        height=width,
        label="Added",
        color="#2A6F97",
    )
    axis.barh(
        [position - width / 2 for position in positions],
        [-by_source[source]["removed"] for source in sources],
        height=width,
        label="Removed",
        color="#B04A4A",
    )
    axis.set_yticks(positions)
    axis.set_yticklabels(sources)
    axis.set_xlabel("Indicator changes; removals are shown below zero")
    axis.set_title("Snapshot comparison by source")
    axis.axvline(0, color="black", linewidth=0.8)
    axis.grid(axis="x", alpha=0.25)
    axis.legend()
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def compare(
    rows: list[dict[str, str]],
    input_path: Path,
    output_root: Path,
    run_id: str,
    previous_day: str | None = None,
    current_day: str | None = None,
) -> tuple[str, Path | None]:
    available_days = sorted({day for row in rows if (day := snapshot_day(row))})
    if len(available_days) < 2 and (previous_day is None or current_day is None):
        status_path = make_status(
            output_root,
            run_id,
            input_path,
            "not_ready",
            available_days,
            "At least two distinct successful snapshot days are required before a comparison can be made.",
        )
        return "not_ready", status_path

    if current_day is None:
        current_day = available_days[-1]
    if previous_day is None:
        candidates = [day for day in available_days if day < current_day]
        previous_day = candidates[-1] if candidates else ""

    if not previous_day or previous_day == current_day:
        status_path = make_status(
            output_root,
            run_id,
            input_path,
            "not_ready",
            available_days,
            "Two different snapshot days were not selected.",
        )
        return "not_ready", status_path

    missing = [day for day in (previous_day, current_day) if day not in available_days]
    if missing:
        status_path = make_status(
            output_root,
            run_id,
            input_path,
            "error",
            available_days,
            f"Requested snapshot day(s) are missing: {', '.join(missing)}.",
        )
        return "error", status_path

    selected_run_dir = output_root / safe_name(run_id)
    comparison_dir = selected_run_dir / f"{previous_day}_vs_{current_day}"
    comparison_dir.mkdir(parents=True, exist_ok=True)

    sources = sorted({row.get("source_name", "") for row in rows if row.get("source_name", "")})
    previous_snapshots = {
        source: latest_snapshot(rows, source, previous_day) for source in sources
    }
    current_snapshots = {
        source: latest_snapshot(rows, source, current_day) for source in sources
    }

    summary_fields = [
        "source",
        "indicator_type",
        "previous_day",
        "current_day",
        "previous_snapshot_id",
        "current_snapshot_id",
        "previous_snapshot_status",
        "current_snapshot_status",
        "previous_retrieved_at_utc",
        "current_retrieved_at_utc",
        "previous_count",
        "current_count",
        "added_count",
        "removed_count",
        "unchanged_count",
        "net_change",
        "percent_change",
        "calendar_gap_days",
        "consecutive_calendar_days",
        "comparison_status",
    ]
    change_fields = [
        "source",
        "indicator_type",
        "indicator",
        "change",
        "previous_day",
        "current_day",
        "previous_snapshot_id",
        "current_snapshot_id",
        "previous_retrieved_at_utc",
        "current_retrieved_at_utc",
        "previous_source_path",
        "current_source_path",
        "previous_sha256",
        "current_sha256",
    ]

    previous_date = date.fromisoformat(previous_day)
    current_date = date.fromisoformat(current_day)
    gap_days = (current_date - previous_date).days
    summary: list[dict[str, object]] = []
    changes: list[dict[str, object]] = []
    types = sorted(
        {
            key[0]
            for snapshot in list(previous_snapshots.values()) + list(current_snapshots.values())
            if snapshot is not None
            for key in snapshot["indicators"]
        }
    )

    for source in sources:
        previous = previous_snapshots[source]
        current = current_snapshots[source]
        previous_indicators = previous["indicators"] if previous else {}
        current_indicators = current["indicators"] if current else {}
        for indicator_type in types:
            previous_keys = {
                key for key in previous_indicators if key[0] == indicator_type
            }
            current_keys = {
                key for key in current_indicators if key[0] == indicator_type
            }
            previous_status = "selected" if previous else "missing"
            current_status = "selected" if current else "missing"
            if previous is None or current is None:
                # Do not interpret a failed or absent source snapshot as an
                # empty list. The source-specific CSV remains available, but
                # the counts are intentionally marked as not comparable.
                summary.append(
                    {
                        "source": source,
                        "indicator_type": indicator_type,
                        "previous_day": previous_day,
                        "current_day": current_day,
                        "previous_snapshot_id": previous.get("snapshot_id", "") if previous else "",
                        "current_snapshot_id": current.get("snapshot_id", "") if current else "",
                        "previous_snapshot_status": previous_status,
                        "current_snapshot_status": current_status,
                        "previous_retrieved_at_utc": previous.get("retrieved_at_utc", "") if previous else "",
                        "current_retrieved_at_utc": current.get("retrieved_at_utc", "") if current else "",
                        "previous_count": len(previous_keys) if previous else "NA",
                        "current_count": len(current_keys) if current else "NA",
                        "added_count": "NA",
                        "removed_count": "NA",
                        "unchanged_count": "NA",
                        "net_change": "NA",
                        "percent_change": "NA",
                        "calendar_gap_days": gap_days,
                        "consecutive_calendar_days": "yes" if gap_days == 1 else "no",
                        "comparison_status": "missing_previous_snapshot" if previous is None else "missing_current_snapshot",
                    }
                )
                continue
            added = current_keys - previous_keys
            removed = previous_keys - current_keys
            unchanged = previous_keys & current_keys
            previous_count = len(previous_keys)
            current_count = len(current_keys)
            percent_change: object = "NA"
            if previous_count:
                percent_change = round(
                    (current_count - previous_count) / previous_count * 100,
                    4,
                )
            summary.append(
                {
                    "source": source,
                    "indicator_type": indicator_type,
                    "previous_day": previous_day,
                    "current_day": current_day,
                    "previous_snapshot_id": previous.get("snapshot_id", "") if previous else "",
                    "current_snapshot_id": current.get("snapshot_id", "") if current else "",
                    "previous_snapshot_status": previous_status,
                    "current_snapshot_status": current_status,
                    "previous_retrieved_at_utc": previous.get("retrieved_at_utc", "") if previous else "",
                    "current_retrieved_at_utc": current.get("retrieved_at_utc", "") if current else "",
                    "previous_count": previous_count,
                    "current_count": current_count,
                    "added_count": len(added),
                    "removed_count": len(removed),
                    "unchanged_count": len(unchanged),
                    "net_change": current_count - previous_count,
                    "percent_change": percent_change,
                    "calendar_gap_days": gap_days,
                    "consecutive_calendar_days": "yes" if gap_days == 1 else "no",
                    "comparison_status": "compared",
                }
            )
            for change, keys in (("added", added), ("removed", removed)):
                for key in sorted(keys):
                    previous_row = previous_indicators.get(key, {})
                    current_row = current_indicators.get(key, {})
                    changes.append(
                        {
                            "source": source,
                            "indicator_type": key[0],
                            "indicator": key[1],
                            "change": change,
                            "previous_day": previous_day,
                            "current_day": current_day,
                            "previous_snapshot_id": previous.get("snapshot_id", "") if previous else "",
                            "current_snapshot_id": current.get("snapshot_id", "") if current else "",
                            "previous_retrieved_at_utc": previous_row.get("retrieved_at_utc", ""),
                            "current_retrieved_at_utc": current_row.get("retrieved_at_utc", ""),
                            "previous_source_path": previous_row.get("source_path", ""),
                            "current_source_path": current_row.get("source_path", ""),
                            "previous_sha256": previous_row.get("sha256", ""),
                            "current_sha256": current_row.get("sha256", ""),
                        }
                    )

    write_rows(comparison_dir / "source_summary.csv", summary_fields, summary)
    write_rows(comparison_dir / "indicator_changes.csv", change_fields, changes)

    source_change_files: list[str] = []
    for source in sources:
        source_rows = [row for row in changes if row["source"] == source]
        source_path = comparison_dir / f"{source_slug(source)}_changes.csv"
        write_rows(source_path, change_fields, source_rows)
        source_change_files.append(relative_path(source_path))

    snapshot_index: list[dict[str, object]] = []
    for role, day, snapshots in (
        ("previous", previous_day, previous_snapshots),
        ("current", current_day, current_snapshots),
    ):
        for source in sources:
            snapshot = snapshots[source]
            snapshot_index.append(
                {
                    "role": role,
                    "source": source,
                    "snapshot_day": day,
                    "status": "selected" if snapshot else "missing",
                    "snapshot_id": snapshot.get("snapshot_id", "") if snapshot else "",
                    "retrieved_at_utc": snapshot.get("retrieved_at_utc", "") if snapshot else "",
                    "source_path": snapshot.get("source_path", "") if snapshot else "",
                    "sha256": snapshot.get("sha256", "") if snapshot else "",
                    "indicator_count": len(snapshot["indicators"]) if snapshot else 0,
                }
            )
    write_rows(
        comparison_dir / "snapshot_index.csv",
        [
            "role",
            "source",
            "snapshot_day",
            "status",
            "snapshot_id",
            "retrieved_at_utc",
            "source_path",
            "sha256",
            "indicator_count",
        ],
        snapshot_index,
    )

    figure_path = comparison_dir / "changes_by_source.png"
    make_figure(summary, figure_path)

    note_lines = [
        f"Generated at UTC: {utc_now()}",
        f"Previous day: {previous_day}",
        f"Current day: {current_day}",
        f"Calendar gap: {gap_days} day(s); consecutive={gap_days == 1}",
        "Selection rule: the latest normalized snapshot for each source on each selected day.",
        "A second run on the same calendar day is not silently counted as another day.",
        "Added and removed indicators use exact canonical (indicator_type, indicator) keys.",
        "If a source snapshot is missing on either selected day, its counts are marked NA rather than treated as removals.",
        "Original raw snapshots, normalized observations and cumulative results are not modified by this comparison.",
        "Use snapshot_index.csv to identify the exact input files and SHA-256 hashes.",
        "Use the source-specific *_changes.csv files when an individual comparison is needed.",
        "List membership is not proof that an indicator is currently malicious.",
    ]
    notes_path = comparison_dir / "comparison_notes.txt"
    notes_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    output_files = [
        comparison_dir / "source_summary.csv",
        comparison_dir / "indicator_changes.csv",
        comparison_dir / "snapshot_index.csv",
        notes_path,
        *[comparison_dir / Path(path).name for path in source_change_files],
    ]
    if figure_path.exists():
        output_files.append(figure_path)
    manifest = {
        "schema_version": 1,
        "status": "created",
        "run_id": run_id,
        "generated_at_utc": utc_now(),
        "input_file": relative_path(input_path),
        "input_sha256": sha256(input_path),
        "previous_day": previous_day,
        "current_day": current_day,
        "calendar_gap_days": gap_days,
        "consecutive_calendar_days": gap_days == 1,
        "selection_rule": "latest snapshot per source/day",
        "sources": sources,
        "missing_source_snapshots": [
            {
                "source": source,
                "previous_status": "selected" if previous_snapshots[source] else "missing",
                "current_status": "selected" if current_snapshots[source] else "missing",
            }
            for source in sources
            if previous_snapshots[source] is None or current_snapshots[source] is None
        ],
        "available_snapshot_days": available_days,
        "summary_rows": len(summary),
        "changed_indicator_rows": len(changes),
        "outputs": [
            {"path": relative_path(path), "sha256": sha256(path)}
            for path in output_files
            if path.exists()
        ],
        "results_directory_untouched": True,
    }
    manifest_path = comparison_dir / "comparison_manifest.json"
    write_json(manifest_path, manifest)

    print(f"comparison_status=created")
    print(f"comparison_previous_day={previous_day}")
    print(f"comparison_current_day={current_day}")
    print(f"comparison_changed_rows={len(changes)}")
    print(f"comparison_dir={relative_path(comparison_dir)}")
    return "created", comparison_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "data/normalized/observations.csv",
        help="Normalized cumulative observations CSV.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "comparisons",
        help="Separate output root for comparison artifacts.",
    )
    parser.add_argument("--previous-day", help="Optional earlier day in YYYY-MM-DD form.")
    parser.add_argument("--current-day", help="Optional later day in YYYY-MM-DD form.")
    parser.add_argument("--run-id", default=None, help="Run ID used in the comparison folder name.")
    args = parser.parse_args()

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not args.input.exists():
        status_path = make_status(
            args.out_dir,
            run_id,
            args.input,
            "error",
            [],
            f"Input file does not exist: {args.input}",
        )
        print(f"comparison_status=error")
        print(f"comparison_status_file={relative_path(status_path)}")
        return 2

    rows = read_rows(args.input)
    status, output_path = compare(
        rows,
        args.input,
        args.out_dir,
        run_id,
        previous_day=args.previous_day,
        current_day=args.current_day,
    )
    if status != "created":
        print(f"comparison_status={status}")
    if output_path is not None and status == "not_ready":
        print(f"comparison_status_file={relative_path(output_path)}")
    return 0 if status in {"created", "not_ready"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
