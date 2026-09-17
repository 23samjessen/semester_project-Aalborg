# Comparison Results Guide

## Purpose

The comparison stage measures how each selected public blocklist changed between two UTC collection dates. It identifies indicators that were added, removed or retained. It does not prove that an indicator is malicious, and it does not scan or contact listed systems.

## Where comparison results are stored

Every comparison has its own independent folder:

```text
comparisons/
â””â”€â”€ <comparison-id>/
    â””â”€â”€ <earlier-date>_vs_<later-date>/
```

Example:

```text
comparisons/
â””â”€â”€ menu_compare_20260917T163338Z/
    â””â”€â”€ 2026-09-16_vs_2026-09-17/
```

The ID identifies the execution that created the comparison. The date-pair folder identifies the two dataset states being compared.

## Files inside a completed comparison

| File | Purpose |
|---|---|
| `source_summary.csv` | Main table: previous count, current count, additions, removals, unchanged values, net change and percentage change for each source and indicator type. |
| `indicator_changes.csv` | Every individual indicator classified as added or removed. |
| `<source>_changes.csv` | Added and removed indicators for one provider only. |
| `snapshot_index.csv` | Exact source snapshots used, including timestamps, paths and SHA-256 hashes. |
| `changes_by_source.png` | Chart of additions and removals by source. |
| `comparison_notes.txt` | Selection method, safeguards and interpretation limitations. |
| `comparison_manifest.json` | Comparison ID, selected dates, input hash, output hashes and missing-source information. |

## How to read `source_summary.csv`

- `previous_count`: number of unique indicators in the earlier snapshot.
- `current_count`: number of unique indicators in the later snapshot.
- `added_count`: indicators found later but not earlier.
- `removed_count`: indicators found earlier but not later.
- `unchanged_count`: indicators present on both dates.
- `net_change`: `current_count - previous_count`.
- `percent_change`: net change relative to the previous count.
- `comparison_status=compared`: both required source snapshots were available.
- `NA` or a missing-snapshot status: the comparison is incomplete for that source and must not be interpreted as mass removal.

The total `changed_indicator_rows` equals the recorded added and removed rows across source/type comparisons. The same indicator can occur in more than one source, so this is not necessarily a globally unique count.

## What the comparison can show

Repeated comparisons across the study period can support analysis of:

1. Turnover: how frequently indicators enter and leave each list.
2. Stability: how many indicators remain unchanged between observations.
3. Source differences: which providers change more or less frequently.
4. Persistence: which indicators continue to appear over several dates.
5. Coverage problems: missing provider snapshots or gaps between collection dates.

These are descriptive findings. A blocklist entry is not proof that an IP address, network or domain is currently malicious. Danish relevance must be established separately using documented evidence and uncertainty labels.

## Commands for the latest example

Run these commands from the project root:

```bash
# Store the comparison folder once to avoid typing the long path repeatedly.
comparison_dir="comparisons/menu_compare_20260917T163338Z/2026-09-16_vs_2026-09-17"

# Confirm which files were created.
find "$comparison_dir" -maxdepth 1 -type f -print | sort

# Read the main statistical summary in a terminal table.
column -s, -t < "$comparison_dir/source_summary.csv" | less -S

# Read the method and interpretation notes.
cat "$comparison_dir/comparison_notes.txt"

# Preview individual added and removed indicators.
head -n 20 "$comparison_dir/indicator_changes.csv"

# Inspect the exact input snapshots and their hashes.
column -s, -t < "$comparison_dir/snapshot_index.csv" | less -S

# Open the complete comparison folder in macOS Finder.
open "$comparison_dir"

# Open the generated chart on macOS.
open "$comparison_dir/changes_by_source.png"
```

Press `q` to leave the `less` viewer.

## Menu workflow

```bash
python scripts/project_menu.py
```

- Option 7 compares today with yesterday.
- Option 8 compares any two available UTC dates.
- Option 12 lists completed comparisons and explains a selected result.
- Option 5 shows collection evidence for a specific day.
- Option 9 shows the files archived for a pipeline run.

## Folder map

```text
data/raw/YYYY-MM-DD/
    Original downloaded evidence for one UTC date.

data/normalized/observations.csv
    Combined, traceable observations produced from all raw snapshots.

results/
    Cumulative analysis across the available study dataset.

comparisons/<comparison-id>/<date-1>_vs_<date-2>/
    Independent comparison between exactly two selected dates.

logs/collection_log.csv
    Global record of source URLs, timestamps, status, sizes, hashes and paths.

logs/validation/
    Timestamped validation reports.

run_records/<run-id>/
    Audit record for one pipeline execution, including logs, manifest and archived outputs.
```

## Recommended daily procedure

1. Run menu option 1 once on the intended UTC collection day.
2. Confirm successful downloads with option 4.
3. Inspect todayâ€™s result with option 3.
4. Run option 6 and record the validation result.
5. Use option 12 to inspect the automatically generated comparison.
6. Record missing feeds, abnormal changes and limitations in the project work log.
7. Do not edit files under `data/raw/` or existing comparison folders.
