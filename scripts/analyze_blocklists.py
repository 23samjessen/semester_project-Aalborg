#!/usr/bin/env python3
"""Create descriptive tables and visualizations from normalized observations."""

from __future__ import annotations

import argparse
import csv
import itertools
import math
from collections import defaultdict
from pathlib import Path


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def source_day(row: dict[str, str]) -> str:
    value = row.get("retrieved_at_utc", "")
    return value[:10] if value else "unknown"


def observation_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("indicator_type", ""), row.get("indicator", "")


def make_daily_summary(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    raw_counts: dict[tuple[str, str], int] = defaultdict(int)
    for item in rows:
        key = (item.get("source_name", ""), source_day(item))
        grouped[key].add(observation_key(item))
        raw_counts[key] += 1

    result: list[dict[str, object]] = []
    for source in sorted({key[0] for key in grouped}):
        previous: set[tuple[str, str]] | None = None
        for source_name, day in sorted(key for key in grouped if key[0] == source):
            current = grouped[(source_name, day)]
            additions = len(current - previous) if previous is not None else "NA"
            removals = len(previous - current) if previous is not None else "NA"
            result.append(
                {
                    "source": source_name,
                    "snapshot_day": day,
                    "unique_indicators": len(current),
                    "unique_ips_cidrs": sum(1 for kind, _ in current if kind in {"ip", "cidr"}),
                    "unique_domains_urls": sum(1 for kind, _ in current if kind in {"domain", "url"}),
                    "additions": additions,
                    "removals": removals,
                    "raw_rows": raw_counts[(source_name, day)],
                }
            )
            previous = current
    return result


def make_persistence(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    snapshots: dict[str, set[str]] = defaultdict(set)
    seen: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for item in rows:
        source = item.get("source_name", "")
        day = source_day(item)
        snapshots[source].add(day)
        indicator_type, indicator = observation_key(item)
        seen[(source, indicator_type, indicator)].add(day)

    result: list[dict[str, object]] = []
    for (source, indicator_type, indicator), days in sorted(seen.items()):
        ordered = sorted(days)
        successful = len(snapshots[source])
        present = len(days)
        result.append(
            {
                "source": source,
                "indicator_type": indicator_type,
                "indicator": indicator,
                "first_seen": ordered[0],
                "last_seen": ordered[-1],
                "snapshots_present": present,
                "successful_snapshots": successful,
                "persistence_ratio": round(present / successful, 6) if successful else "NA",
                "right_censored": "yes" if ordered[-1] == max(snapshots[source]) else "no",
            }
        )
    return result


def make_overlap(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    sets: dict[tuple[str, str], set[str]] = defaultdict(set)
    for item in rows:
        source = item.get("source_name", "")
        indicator_type = item.get("indicator_type", "")
        indicator = item.get("indicator", "")
        sets[(source, indicator_type)].add(indicator)

    result: list[dict[str, object]] = []
    keys = sorted(sets)
    for left, right in itertools.combinations(keys, 2):
        if left[1] != right[1]:
            continue
        intersection = sets[left] & sets[right]
        union = sets[left] | sets[right]
        result.append(
            {
                "source_a": left[0],
                "source_b": right[0],
                "indicator_type": left[1],
                "intersection": len(intersection),
                "union": len(union),
                "jaccard": round(len(intersection) / len(union), 6) if union else "NA",
                "comparison_note": "exact canonical representation over the full observation window",
            }
        )
    return result


def make_figures(daily: list[dict[str, object]], overlap: list[dict[str, object]], out_dir: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        (out_dir / "analysis_notes.txt").write_text(
            "matplotlib is not installed; install requirements.txt to generate figures.\n",
            encoding="utf-8",
        )
        return

    if not daily:
        (out_dir / "analysis_notes.txt").write_text(
            "No normalized observations were available; no empirical figure was generated.\n",
            encoding="utf-8",
        )
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    sources = sorted({str(item["source"]) for item in daily})
    fig, axis = plt.subplots(figsize=(10, 5.5))
    for source in sources:
        subset = [item for item in daily if item["source"] == source]
        axis.plot(
            [str(item["snapshot_day"]) for item in subset],
            [int(item["unique_indicators"]) for item in subset],
            marker="o",
            linewidth=1.6,
            label=source,
        )
    axis.set_title("Unique canonical indicators per successful snapshot")
    axis.set_xlabel("Snapshot day")
    axis.set_ylabel("Unique indicators")
    axis.tick_params(axis="x", rotation=45)
    axis.grid(alpha=0.25)
    axis.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "daily_unique_indicators.png", dpi=180)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(10, 5.5))
    for source in sources:
        subset = [item for item in daily if item["source"] == source and item["additions"] != "NA"]
        axis.plot(
            [str(item["snapshot_day"]) for item in subset],
            [int(item["additions"]) for item in subset],
            marker="o",
            linewidth=1.4,
            label=f"{source} additions",
        )
        axis.plot(
            [str(item["snapshot_day"]) for item in subset],
            [-int(item["removals"]) for item in subset],
            marker="x",
            linestyle="--",
            linewidth=1.2,
            label=f"{source} removals",
        )
    axis.axhline(0, color="black", linewidth=0.8)
    axis.set_title("Daily additions and removals; removals shown below zero")
    axis.set_xlabel("Snapshot day")
    axis.set_ylabel("Change from preceding successful snapshot")
    axis.tick_params(axis="x", rotation=45)
    axis.grid(alpha=0.25)
    axis.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "daily_additions_removals.png", dpi=180)
    plt.close(fig)

    if overlap:
        comparable = [item for item in overlap if item["jaccard"] != "NA"]
        labels = [f"{item['source_a']} / {item['source_b']}\n{item['indicator_type']}" for item in comparable]
        values = [float(item["jaccard"]) for item in comparable]
        fig, axis = plt.subplots(figsize=(10, max(4, len(labels) * 0.45)))
        axis.barh(labels, values, color="#2a5d88")
        axis.set_xlim(0, 1)
        axis.set_xlabel("Jaccard similarity")
        axis.set_title("Exact canonical overlap across the observation window")
        axis.grid(axis="x", alpha=0.25)
        fig.tight_layout()
        fig.savefig(out_dir / "source_overlap.png", dpi=180)
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows = read_rows(args.input)
    daily = make_daily_summary(rows)
    persistence = make_persistence(rows)
    overlap = make_overlap(rows)

    write_rows(
        args.out_dir / "daily_summary.csv",
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
        daily,
    )
    write_rows(
        args.out_dir / "persistence.csv",
        [
            "source",
            "indicator_type",
            "indicator",
            "first_seen",
            "last_seen",
            "snapshots_present",
            "successful_snapshots",
            "persistence_ratio",
            "right_censored",
        ],
        persistence,
    )
    write_rows(
        args.out_dir / "overlap.csv",
        [
            "source_a",
            "source_b",
            "indicator_type",
            "intersection",
            "union",
            "jaccard",
            "comparison_note",
        ],
        overlap,
    )
    make_figures(daily, overlap, args.out_dir)

    (args.out_dir / "analysis_notes.txt").write_text(
        "These outputs are descriptive. Confirm source semantics, missing snapshots, parser errors, country evidence and representation level before writing conclusions.\n"
        "Do not interpret list membership as proof of current maliciousness or current ownership.\n",
        encoding="utf-8",
    )
    print(f"wrote {len(daily)} daily rows, {len(persistence)} persistence rows and {len(overlap)} overlap rows to {args.out_dir}")


if __name__ == "__main__":
    main()
