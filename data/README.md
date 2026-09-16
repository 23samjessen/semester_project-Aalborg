# Data handling

`raw/` contains immutable provider snapshots. `normalized/` contains derived observations. The current package may contain a one-day baseline created to test the parser; it is not the project’s required 30-day dataset and must not be presented as final findings.

For normal daily operation, run the complete pipeline from the project root:

```bash
python scripts/run_daily_pipeline.py
```

The command keeps the data layers separate:

- `data/raw/YYYY-MM-DD/` stores the original response files and never overwrites an earlier snapshot;
- `data/normalized/observations.csv` is the cumulative, regenerated table;
- `results/` contains cumulative analysis outputs;
- `run_records/<run-id>/` contains the timestamped audit record and a copy of the analysis produced by that run;
- `comparisons/<run-id>/` contains only the comparison between two distinct dates.

The comparison folder is deliberately outside `results/`. If a comparison has a coding error, delete or regenerate only that comparison folder after checking the manifest; the raw evidence and cumulative results remain independent.

Every run uses UTC timestamps. A second run on the same calendar day is retained as a separate snapshot, but it is not silently counted as another study day. The comparison selects the latest snapshot for each source on each of the two selected dates.

If a provider is missing on one selected date, the comparison records that gap and uses `NA` for its change counts. A missing or failed source snapshot is never treated as evidence that all of its previous indicators were removed.

Before classification, copy the two templates and fill them with evidence that the group actually retrieved:

```bash
cp data/danish_evidence_template.csv data/danish_evidence.csv
cp data/danish_prefixes_template.csv data/danish_prefixes.csv
```

Keep the source URL, access date and retrieval timestamp in the evidence file. Do not put API keys or private correspondence in these files.
