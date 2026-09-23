#!/usr/bin/env python3
"""Display a saved daily summary and export a dated figure without collecting data."""

import argparse
import csv
import hashlib
import io
import json
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ["source", "snapshot_day", "unique_indicators", "unique_ips_cidrs",
          "unique_domains_urls", "additions", "removals", "raw_rows"]
DISPLAY = [FIELDS[0], *FIELDS[2:]]
LABELS = ["Source", "Unique", "IPs/CIDRs", "Domains/URLs", "Added", "Removed", "Raw rows"]
NOTES = (
    "Values are copied from saved analysis; no new collection or calculation was performed.\n"
    "NA or blank means unavailable/not applicable, not zero. Check logs for collection coverage.\n"
    "Additions/removals retain the comparison method used by the original analysis.\n"
    "This table alone does not establish Danish relevance or current maliciousness."
)


def checked_date(value):
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError("Use the complete date format YYYY-MM-DD.")
    return value


def make_image(path, day, exported, rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(13, 4.4 + 0.3 * len(rows)))
    ax.axis("off")
    fig.subplots_adjust(left=0.025, right=0.975, top=0.70, bottom=0.26)
    fig.text(0.03, 0.92, f"Saved daily results | UTC observation date: {day}",
             fontsize=17, weight="bold", color="#183b56")
    fig.text(0.03, 0.85, f"Exported at {exported} | Redisplayed from saved analysis",
             fontsize=10)
    fig.text(0.03, 0.79, "Source: results/daily_summary.csv | Full source and hash saved with this figure",
             fontsize=9)
    table = ax.table(cellText=[[row[key] for key in DISPLAY] for row in rows],
                     colLabels=LABELS, loc="center", cellLoc="center",
                     colWidths=[0.23, 0.12, 0.14, 0.15, 0.11, 0.12, 0.13])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#d8e0e8")
        if r == 0:
            cell.set_facecolor("#183b56")
            cell.set_text_props(color="white", weight="bold")
        else:
            cell.set_facecolor("#f0f4f8" if r % 2 else "white")
    fig.text(0.03, 0.05, NOTES, fontsize=9, linespacing=1.5)
    fig.savefig(path, dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="A saved UTC date, for example 2026-09-16")
    parser.add_argument("--list-dates", action="store_true")
    args = parser.parse_args(argv)

    source = ROOT / "results" / "daily_summary.csv"
    if not source.is_file():
        print(f"Saved summary not found: {source}")
        print("Inspect saved raw files/run records before replaying analysis with menu option 2.")
        return 1

    original = source.read_bytes()
    reader = csv.DictReader(io.StringIO(original.decode("utf-8-sig")))
    fields = reader.fieldnames or []
    if not set(FIELDS).issubset(fields) or len(set(fields)) != len(fields):
        raise ValueError("The daily summary has missing or duplicate column names.")

    rows = list(reader)
    for line, row in enumerate(rows, 2):
        if None in row or any(row.get(key) is None for key in fields):
            raise ValueError(f"Malformed CSV record near row {line}; no export created.")
        checked_date(row["snapshot_day"])

    dates = sorted({row["snapshot_day"] for row in rows})
    if not dates:
        print("The daily summary contains no saved dates.")
        return 1

    print("\nAVAILABLE SAVED UTC DATES\n" + "\n".join(dates))
    if args.list_dates:
        return 0

    day = args.date
    if day is None:
        day = input(f"\nEnter date [{dates[-1]}], or Q to cancel: ").strip()
        if day.upper() == "Q":
            return 0
        day = day or dates[-1]

    checked_date(day)
    selected = [row for row in rows if row["snapshot_day"] == day]
    if not selected:
        print(f"No result for {day} is present in {source}.")
        print("Use menu option 5 to check its collection log. Missing data is not recreated here.")
        return 1

    names = [row["source"] for row in selected]
    if any(not name.strip() for name in names) or len(set(names)) != len(names):
        raise ValueError("Empty or repeated source for this date; inspect the summary before exporting.")

    now = datetime.now(timezone.utc)
    exported = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    export_id = now.strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid4().hex[:6]
    output = ROOT / "report_exports" / "daily_results" / day / export_id

    values = [[row[key] for key in DISPLAY] for row in selected]
    widths = [max(len(label), *(len(row[i]) for row in values))
              for i, label in enumerate(LABELS)]
    table = "\n".join(" | ".join(value.ljust(widths[i]) for i, value in enumerate(row))
                      for row in [LABELS, *values])

    digest = hashlib.sha256(original).hexdigest()
    text = (f"SAVED DAILY RESULT\nObservation date (UTC): {day}\nExported at (UTC): {exported}\n"
            f"Source: {source}\n\n{table}\n\n{NOTES}\n\nSource SHA-256: {digest}\n")
    print("\n" + text)

    output.mkdir(parents=True, exist_ok=False)
    (output / "source_daily_summary.csv").write_bytes(original)
    with (output / "daily_result.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(selected)
    (output / "daily_result.txt").write_text(text, encoding="utf-8")

    image_error = None
    try:
        make_image(output / "daily_result.png", day, exported, selected)
    except Exception as exc:
        image_error = str(exc)
        print(f"Image export failed: {exc}. The CSV and text files are still saved.")

    manifest = {
        "observation_date_utc": day,
        "exported_at_utc": exported,
        "export_id": export_id,
        "source_path": str(source),
        "source_sha256": digest,
        "source_rows_exported": len(selected),
        "network_requests": 0,
        "method": "Filter existing daily summary by snapshot_day; no recalculation.",
        "image_error": image_error,
    }
    (output / "export_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"SAVED FOLDER: {output}\n")
    for item in sorted(output.iterdir()):
        print(f"  {item.name}")
    if image_error is None:
        print("\nUse daily_result.png in the report, with its observation date and export time.")
    print("Mac: exit the menu and run: open report_exports/daily_results")
    return 0 if image_error is None else 1


def run(argv=None):
    try:
        return main(argv)
    except (EOFError, KeyboardInterrupt):
        print("\nDisplay cancelled.")
        return 1
    except (OSError, ValueError, csv.Error) as exc:
        print(f"Unable to display saved results: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
