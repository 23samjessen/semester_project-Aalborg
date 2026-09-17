#!/usr/bin/env python3
"""Generate a non-destructive final or preview study evidence package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DAYS = 30


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(
    path: Path,
    fields: list[str],
    rows: list[dict[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def observation_day(row: dict[str, str]) -> str:
    candidate = row.get("retrieved_at_utc", "")[:10]

    try:
        return date.fromisoformat(candidate).isoformat()
    except ValueError:
        return ""


def to_integer(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def find_missing_days(days: list[str]) -> list[str]:
    if len(days) < 2:
        return []

    first = date.fromisoformat(days[0])
    last = date.fromisoformat(days[-1])
    available = set(days)

    missing: list[str] = []
    current = first

    while current <= last:
        value = current.isoformat()

        if value not in available:
            missing.append(value)

        current += timedelta(days=1)

    return missing


def calculate_source_statistics(
    daily_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in daily_rows:
        grouped[row.get("source", "unknown")].append(row)

    results: list[dict[str, object]] = []

    for source, rows in sorted(grouped.items()):
        rows.sort(key=lambda row: row.get("snapshot_day", ""))

        counts = [
            number
            for row in rows
            if (
                number := to_integer(
                    row.get("unique_indicators", "")
                )
            )
            is not None
        ]

        additions = [
            number
            for row in rows
            if (
                number := to_integer(row.get("additions", ""))
            )
            is not None
        ]

        removals = [
            number
            for row in rows
            if (
                number := to_integer(row.get("removals", ""))
            )
            is not None
        ]

        results.append(
            {
                "source": source,
                "observed_days": len(
                    {
                        row.get("snapshot_day", "")
                        for row in rows
                    }
                ),
                "first_day": (
                    rows[0].get("snapshot_day", "")
                    if rows
                    else ""
                ),
                "last_day": (
                    rows[-1].get("snapshot_day", "")
                    if rows
                    else ""
                ),
                "minimum_indicators": (
                    min(counts) if counts else "NA"
                ),
                "maximum_indicators": (
                    max(counts) if counts else "NA"
                ),
                "mean_indicators": (
                    round(statistics.mean(counts), 4)
                    if counts
                    else "NA"
                ),
                "total_additions": sum(additions),
                "total_removals": sum(removals),
                "mean_daily_additions": (
                    round(statistics.mean(additions), 4)
                    if additions
                    else "NA"
                ),
                "mean_daily_removals": (
                    round(statistics.mean(removals), 4)
                    if removals
                    else "NA"
                ),
            }
        )

    return results


def collect_comparison_statistics() -> list[dict[str, object]]:
    comparison_root = ROOT / "comparisons"
    newest_by_pair: dict[
        tuple[str, str],
        dict[str, object],
    ] = {}

    if not comparison_root.exists():
        return []

    for manifest_path in comparison_root.glob(
        "*/*/comparison_manifest.json"
    ):
        try:
            payload = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            continue

        previous_day = str(
            payload.get("previous_day", "")
        )
        current_day = str(
            payload.get("current_day", "")
        )

        if not previous_day or not current_day:
            continue

        payload["manifest_path"] = str(
            manifest_path.relative_to(ROOT)
        )

        pair = (previous_day, current_day)
        existing = newest_by_pair.get(pair)

        if (
            existing is None
            or str(payload.get("generated_at_utc", ""))
            > str(existing.get("generated_at_utc", ""))
        ):
            newest_by_pair[pair] = payload

    results: list[dict[str, object]] = []

    for pair, payload in sorted(newest_by_pair.items()):
        previous_day, current_day = pair

        results.append(
            {
                "previous_day": previous_day,
                "current_day": current_day,
                "comparison_id": payload.get(
                    "run_id",
                    "",
                ),
                "status": payload.get(
                    "status",
                    "unknown",
                ),
                "changed_indicator_rows": payload.get(
                    "changed_indicator_rows",
                    "",
                ),
                "consecutive_calendar_days": payload.get(
                    "consecutive_calendar_days",
                    "",
                ),
                "missing_source_snapshot_count": len(
                    payload.get(
                        "missing_source_snapshots",
                        [],
                    )
                ),
                "manifest_path": payload.get(
                    "manifest_path",
                    "",
                ),
            }
        )

    return results


def copy_evidence(
    destination: Path,
    source_paths: list[Path],
) -> None:
    destination.mkdir(parents=True, exist_ok=True)

    for source_path in source_paths:
        if source_path.exists():
            shutil.copy2(
                source_path,
                destination / source_path.name,
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    parser.add_argument(
        "--allow-preview",
        action="store_true",
        help="Allow generation before 30 distinct days.",
    )

    args = parser.parse_args()

    observations_path = (
        ROOT / "data/normalized/observations.csv"
    )
    observations = read_csv(observations_path)

    if not observations:
        print("final_status=error")
        print(
            "final_reason=normalized observations "
            "are missing or empty"
        )
        return 2

    days = sorted(
        {
            day
            for row in observations
            if (day := observation_day(row))
        }
    )

    ready = len(days) >= REQUIRED_DAYS

    if not ready and not args.allow_preview:
        print("final_status=not_ready")
        print(f"available_days={len(days)}")
        print(f"required_days={REQUIRED_DAYS}")
        print(
            f"remaining_days="
            f"{REQUIRED_DAYS - len(days)}"
        )
        return 3

    generated_at = utc_now()
    package_type = "final" if ready else "preview"

    package_id = (
        f"{package_type}_"
        f"{generated_at.strftime('%Y%m%dT%H%M%SZ')}"
    )

    output_directory = (
        ROOT / "final_results" / package_id
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    daily_rows = read_csv(
        ROOT / "results/daily_summary.csv"
    )
    persistence_rows = read_csv(
        ROOT / "results/persistence.csv"
    )
    overlap_rows = read_csv(
        ROOT / "results/overlap.csv"
    )
    parser_errors = read_csv(
        ROOT / "logs/normalization_errors.csv"
    )
    collection_rows = read_csv(
        ROOT / "logs/collection_log.csv"
    )

    danish_path = (
        ROOT / "results/danish_classification.csv"
    )
    danish_rows = read_csv(danish_path)

    missing_days = find_missing_days(days)
    source_statistics = calculate_source_statistics(
        daily_rows
    )
    comparison_statistics = (
        collect_comparison_statistics()
    )

    indicator_types = Counter(
        row.get("indicator_type", "unknown")
        for row in observations
    )

    source_counts = Counter(
        row.get("source_name", "unknown")
        for row in observations
    )

    collection_statuses = Counter(
        row.get("status", "unknown")
        for row in collection_rows
    )

    write_csv(
        output_directory / "source_statistics.csv",
        (
            list(source_statistics[0].keys())
            if source_statistics
            else ["source"]
        ),
        source_statistics,
    )

    write_csv(
        output_directory / "comparison_coverage.csv",
        (
            list(comparison_statistics[0].keys())
            if comparison_statistics
            else ["previous_day", "current_day"]
        ),
        comparison_statistics,
    )

    write_csv(
        output_directory
        / "missing_calendar_days.csv",
        ["missing_day"],
        [
            {"missing_day": missing_day}
            for missing_day in missing_days
        ],
    )

    quality_rows = [
        {
            "check": "30-day coverage",
            "status": "PASS" if ready else "WARN",
            "value": len(days),
            "interpretation": (
                "At least 30 distinct UTC dates "
                "are required."
            ),
        },
        {
            "check": "calendar gaps",
            "status": (
                "PASS" if not missing_days else "WARN"
            ),
            "value": len(missing_days),
            "interpretation": (
                "Missing dates between the first "
                "and last observed date."
            ),
        },
        {
            "check": "parser notes",
            "status": (
                "PASS" if not parser_errors else "WARN"
            ),
            "value": len(parser_errors),
            "interpretation": (
                "Review parser notes before reporting."
            ),
        },
        {
            "check": "Danish classification",
            "status": (
                "PASS" if danish_rows else "WARN"
            ),
            "value": len(danish_rows),
            "interpretation": (
                "Required for Danish-specific claims."
            ),
        },
        {
            "check": "domain observations",
            "status": (
                "PASS"
                if indicator_types.get("domain", 0)
                else "WARN"
            ),
            "value": indicator_types.get("domain", 0),
            "interpretation": (
                "Do not claim empirical domain analysis "
                "when this value is zero."
            ),
        },
        {
            "check": "comparison coverage",
            "status": (
                "PASS"
                if len(comparison_statistics)
                >= max(0, len(days) - 1)
                else "WARN"
            ),
            "value": len(comparison_statistics),
            "interpretation": (
                "Normally one unique comparison is "
                "expected for each adjacent date pair."
            ),
        },
    ]

    write_csv(
        output_directory / "data_quality_report.csv",
        [
            "check",
            "status",
            "value",
            "interpretation",
        ],
        quality_rows,
    )

    evidence_directory = (
        output_directory / "evidence_tables"
    )

    copy_evidence(
        evidence_directory,
        [
            ROOT / "results/daily_summary.csv",
            ROOT / "results/persistence.csv",
            ROOT / "results/overlap.csv",
            ROOT
            / "results/danish_classification.csv",
            ROOT
            / "logs/normalization_errors.csv",
        ],
    )

    figures_directory = (
        output_directory / "figures"
    )
    figures_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    results_directory = ROOT / "results"

    if results_directory.exists():
        for figure_path in results_directory.glob(
            "*.png"
        ):
            shutil.copy2(
                figure_path,
                figures_directory / figure_path.name,
            )

    manual_requirements = [
        (
            "Provider listing criteria and intelligence "
            "sources require cited policy research."
        ),
        (
            "Indicator-specific listing reasons must only "
            "be reported when supported by evidence."
        ),
        (
            "Delisting difficulty requires a policy matrix "
            "or an authorized practical case."
        ),
        (
            "Danish attribution requires documented "
            "evidence and uncertainty labels."
        ),
        (
            "Blocklist membership is not proof of current "
            "malicious activity."
        ),
    ]

    (
        output_directory
        / "MANUAL_RESEARCH_REQUIRED.txt"
    ).write_text(
        "\n".join(manual_requirements) + "\n",
        encoding="utf-8",
    )

    summary_lines = [
        (
            "# Final Study Evidence Package"
            if ready
            else "# Preliminary Study Evidence Package"
        ),
        "",
        (
            "- Package status: "
            + (
                "**FINAL DATASET READY**"
                if ready
                else "**PREVIEW — NOT FINAL**"
            )
        ),
        (
            "- Generated at UTC: "
            + generated_at.isoformat().replace(
                "+00:00",
                "Z",
            )
        ),
        (
            f"- Distinct UTC collection dates: "
            f"{len(days)} of required {REQUIRED_DAYS}"
        ),
        (
            f"- Observed period: "
            f"{days[0]} to {days[-1]}"
        ),
        (
            f"- Normalized observations: "
            f"{len(observations)}"
        ),
        (
            f"- Missing calendar dates: "
            f"{len(missing_days)}"
        ),
        (
            f"- Unique comparison pairs: "
            f"{len(comparison_statistics)}"
        ),
        f"- Parser notes: {len(parser_errors)}",
        (
            f"- Persistence rows: "
            f"{len(persistence_rows)}"
        ),
        f"- Overlap rows: {len(overlap_rows)}",
        (
            f"- Danish classification rows: "
            f"{len(danish_rows)}"
        ),
        "",
        "## Source observations",
        "",
    ]

    for source, count in sorted(
        source_counts.items()
    ):
        summary_lines.append(
            f"- {source}: {count} normalized rows"
        )

    summary_lines.extend(
        [
            "",
            "## Indicator types",
            "",
        ]
    )

    for indicator_type, count in sorted(
        indicator_types.items()
    ):
        summary_lines.append(
            f"- {indicator_type}: {count}"
        )

    summary_lines.extend(
        [
            "",
            "## Collection status",
            "",
        ]
    )

    for status, count in sorted(
        collection_statuses.items()
    ):
        summary_lines.append(
            f"- {status}: {count}"
        )

    summary_lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            (
                "This package provides reproducible "
                "quantitative evidence. Provider motives, "
                "listing reasons, policy transparency and "
                "delisting difficulty require cited manual "
                "research. Blocklist membership alone is "
                "not proof of malicious activity."
            ),
        ]
    )

    summary_path = (
        output_directory / "FINAL_STUDY_SUMMARY.md"
    )

    summary_path.write_text(
        "\n".join(summary_lines) + "\n",
        encoding="utf-8",
    )

    evidence_rows: list[dict[str, object]] = []

    for file_path in sorted(
        path
        for path in output_directory.rglob("*")
        if path.is_file()
    ):
        evidence_rows.append(
            {
                "path": str(
                    file_path.relative_to(
                        output_directory
                    )
                ),
                "bytes": file_path.stat().st_size,
                "sha256": file_hash(file_path),
            }
        )

    write_csv(
        output_directory / "evidence_index.csv",
        ["path", "bytes", "sha256"],
        evidence_rows,
    )

    manifest = {
        "schema_version": 1,
        "package_id": package_id,
        "status": "final" if ready else "preview",
        "generated_at_utc": (
            generated_at.isoformat().replace(
                "+00:00",
                "Z",
            )
        ),
        "required_distinct_days": REQUIRED_DAYS,
        "available_distinct_days": len(days),
        "available_days": days,
        "missing_calendar_days": missing_days,
        "normalized_rows": len(observations),
        "indicator_types": dict(indicator_types),
        "sources": dict(source_counts),
        "comparison_pairs": len(
            comparison_statistics
        ),
        "danish_classification_available": bool(
            danish_rows
        ),
        "domain_observations_available": (
            indicator_types.get("domain", 0) > 0
        ),
        "outputs": evidence_rows,
    }

    (
        output_directory / "final_manifest.json"
    ).write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "final_status="
        + (
            "created"
            if ready
            else "preview_created"
        )
    )
    print(f"available_days={len(days)}")
    print(f"required_days={REQUIRED_DAYS}")
    print(
        "final_package="
        + str(output_directory.relative_to(ROOT))
    )
    print(
        "final_summary="
        + str(summary_path.relative_to(ROOT))
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
