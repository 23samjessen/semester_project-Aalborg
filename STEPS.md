# Project steps

Use these steps from the project root. The complete commented command list is in `README.md`, and the Word version is `report/Blocklist_Project_Command_Runbook.docx`.

## 1. Open the project in VS Code

```bash
cd /absolute/path/to/Blocklist_Danish_Project_Package
code .
```

The project root is the folder containing `README.md`, `requirements.txt` and `scripts/`.

## 2. Create the Python environment

Run this once on each computer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The environment keeps the project libraries separate from the rest of the computer.

## 3. Set the responsible contact string

Replace the example email with a group-controlled address:

```bash
export BLOCKLIST_USER_AGENT='AAU-blocklist-study/0.1 contact: GROUP-EMAIL'
```

## 4. Run the complete daily pipeline

Use this command once per collection day:

```bash
python scripts/run_daily_pipeline.py
```

It performs these actions in order:

1. Downloads the enabled public feeds.
2. Saves immutable raw files under `data/raw/YYYY-MM-DD/`.
3. Normalizes all available raw files into `data/normalized/observations.csv`.
4. Recalculates the cumulative tables and figures in `results/`.
5. Archives a copy of that analysis under `run_records/<run-id>/analysis/`.
6. Compares the latest two distinct dates under `comparisons/`.
7. Runs the local validation checklist and saves `validation_report.json` inside the run record.

The same run also creates `run_manifest.json`, `run_events.csv`, command logs, `collection.csv`, parser notes and `run_summary.md`. All timestamps are UTC.

On the first day, `comparison_status=not_ready` is expected. On the second distinct day, `comparison_status=created` should appear.

To rerun analysis from the existing raw files without downloading again:

```bash
python scripts/run_daily_pipeline.py --skip-collection
```

## 4.1 Beginner menu

If some group members do not want to remember commands, run:

```bash
python scripts/project_menu.py
```

The menu shows the local Mac time and the canonical UTC date. It explains every choice. Option `1` runs the complete pipeline, option `3` displays today’s result, option `4` shows today’s collection log, option `5` shows a chosen date, option `6` runs validation, option `7` compares today with yesterday, option `8` compares two chosen dates, option `9` opens an archived run, option `10` creates a backup ZIP and option `11` shows project status. Only option `1` makes network requests.

## 5. Optional manual component commands

Use the following commands only when testing one stage or troubleshooting. The normal daily command is Step 4.

```bash
bash scripts/collect_snapshots.sh
```

The command saves enabled public feeds under `data/raw/YYYY-MM-DD/`, creates a per-run collection log under `run_records/`, and writes status, URL, byte count and SHA-256 information to `logs/collection_log.csv`.

Enabled sources are FireHOL Level 2, Spamhaus DROP and blocklist.de. URLhaus is disabled until the group checks the current access route and terms.

## 6. Normalize the raw files

```bash
python scripts/normalize_snapshot.py --raw-dir data/raw --out data/normalized/observations.csv --errors logs/normalization_errors.csv
```

This creates one common, traceable CSV file. It does not edit the raw files.

Check the parser notes:

```bash
cat logs/normalization_errors.csv
```

If the file contains only `path,error`, no parser notes were recorded.

## 7. Analyze the observations

```bash
python scripts/analyze_blocklists.py --input data/normalized/observations.csv --out-dir results
```

This creates daily counts, additions, removals, persistence, overlap and PNG figures in `results/`.

Read the main summary:

```bash
column -s, -t < results/daily_summary.csv
cat results/overlap.csv
```

Compare the latest two distinct dates without changing `results/`:

```bash
python scripts/compare_snapshots.py --input data/normalized/observations.csv --out-dir comparisons
```

The comparison folder contains a manifest, exact input snapshot index, source summary, complete added/removed indicator records, one change file per source and a figure.

If a source is missing on one selected day, its summary is marked as missing and its change counts are `NA`; the program does not mistake a failed or missing source snapshot for removals.

## 7.1 Validate and back up the project

The complete pipeline runs validation automatically. To run it separately:

```bash
python scripts/validate_project.py
```

To create a timestamped backup containing the code, reports, raw snapshots, results, logs, run records and comparisons:

```bash
python scripts/archive_project.py
```

No Docker or database is required for this project. The file layers and their hashes are the evidence store; the backup ZIP is the optional extra protection against losing the folder.

## 8. Add Danish evidence

Member 4 creates editable evidence files from the templates:

```bash
cp data/danish_evidence_template.csv data/danish_evidence.csv
cp data/danish_prefixes_template.csv data/danish_prefixes.csv
code data/danish_evidence.csv
code data/danish_prefixes.csv
```

Enter only evidence that has a source, access date or timestamp and a note about uncertainty. Then run:

```bash
python scripts/classify_danish.py --input data/normalized/observations.csv --evidence data/danish_evidence.csv --prefixes data/danish_prefixes.csv --out results/danish_classification.csv
```

The labels are `DK-supported`, `DK-weak`, `Conflicting` and `Unknown`. These describe Danish evidence, not criminality.

## 9. Repeat daily for at least 30 dates

Member 3 repeats Step 4 each day at the same agreed UTC time. The run record automatically preserves the time, status, data hash and analysis. Keep a note of failed downloads and missing dates in the group log.

Thirty distinct dates are needed because one snapshot cannot measure persistence, turnover or removals over time.

## 10. Optional low-level checks

```bash
bash -n scripts/collect_snapshots.sh
python -m py_compile build_report.py make_colleague_explainer.py scripts/normalize_snapshot.py scripts/analyze_blocklists.py scripts/compare_snapshots.py scripts/run_daily_pipeline.py scripts/classify_danish.py
find data/raw -type f -exec shasum -a 256 {} + | sort > logs/raw_hash_register.txt
```

## 11. Build the Word report

```bash
python build_report.py
```

The report framework contains the academic order: introduction, technical background/dissection, literature review, methodology, findings, analysis/discussion, conclusion, IEEE references, index, diagrams, visualizations and appendices.

## 12. Daily handoff

Member 3 sends the group:

- the newest `run_records/<run-id>/run_summary.md`;
- `run_records/<run-id>/run_manifest.json` if someone needs the full audit trail;
- the comparison folder named in the manifest, when `comparison_status=created`;
- any explanation for a failed source or missing day.

Member 4 sends evidence and classification. Member 5 uses regenerated result files for the figures. Member 6 connects verified findings to policy and limitations. Member 1 integrates the report, while Member 2 maintains the literature and IEEE references.

## 13. Stop the environment

```bash
deactivate
```
