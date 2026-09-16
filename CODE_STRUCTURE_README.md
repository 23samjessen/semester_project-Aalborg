# Code structure and program explanation

This file explains the program in ordinary language so each group member can describe the code during a meeting or project defence.

## The program in one sentence

The program takes dated public blocklist files, preserves the originals, converts different feed formats into one common CSV table, and calculates descriptive statistics that the group can use in the report.

It is a reproducible data pipeline, not a network scanner. It does not scan the Mac address `192.168.0.161`, probe the listed IP addresses, test whether a host is vulnerable, or prove that an indicator is currently malicious.

## The data flow

```text
public HTTPS feeds -> data/raw/ -> observations.csv -> results/ and run_records/ -> comparisons/ -> academic report
```

Each stage has one clear job:

1. The collector downloads one snapshot and records the time, URL, HTTP status, size and SHA-256 hash.
2. The normalizer reads the original files and gives their entries a common structure.
3. The analyzer groups observations by source and day, then calculates counts, persistence and overlap.
4. The comparison module selects the latest snapshots from two distinct days and writes only to `comparisons/`.
5. The daily runner records all commands, timestamps, hashes, statuses and analysis copies in `run_records/`.
6. The Danish classifier reads evidence prepared by the group and applies transparent labels.
7. The validation module checks the project files, data integrity, result files and archives without making network requests.
8. The menu gives beginners numbered choices for running, viewing, comparing, validating and backing up the project.
9. The report builder places the project explanation, tables, figures, references and index into a Word document.

## How we created the Python program

We built it in small stages so that one error does not hide another:

1. We first defined the research unit: one indicator from one source at one collection time.
2. We wrote the shell collector because `curl` is simple and reliable for saving public files. The collector keeps original snapshots instead of editing them.
3. We wrote the normalizer with Python’s standard-library `ipaddress`, `json`, `csv` and `pathlib` modules. This gives FireHOL, Spamhaus and blocklist.de one common schema.
4. We wrote the analyzer using ordinary Python collections and sets. Sets make it possible to count unique indicators and compare exact canonical values between sources.
5. We wrote the Danish classifier separately. It does not silently perform lookups; a group member must enter the evidence source, timestamp and uncertainty first.
6. We wrote the comparison module so a day-to-day difference is reproducible and cannot overwrite cumulative results.
7. We wrote the daily runner last. It calls the existing stages in a fixed order and archives their outputs with UTC timestamps.
8. We wrote the report builder last. It reads the local tables and inserts the verified values into the academic report framework.

This separation makes the work reviewable: Member 3 can prove how a raw file became a normalized row, Member 4 can prove why an indicator received a Danish label, and Member 5 can prove how a chart was calculated.

## Which sites or APIs are connected?

The current collector uses public HTTPS feed URLs with `curl`. It does not use an authenticated API key in the current run.

| Source | Current URL or feed | What the program uses it for |
|---|---|---|
| FireHOL | `https://raw.githubusercontent.com/firehol/blocklist-ipsets/master/firehol_level2.netset` | Public IP/CIDR snapshot for the FireHOL Level 2 list |
| Spamhaus DROP | `https://www.spamhaus.org/drop/drop_v4.json` | Public DROP IPv4 snapshot and provider values such as reason or timestamp when present |
| blocklist.de | `https://lists.blocklist.de/lists/all.txt` | Public text snapshot of reported attack-source IP addresses |
| URLhaus | Optional; disabled in the current run | Not collected until the group checks the official route, terms and any required authentication |

The installed packages `requests`, `dnspython`, `ipwhois` and `tldextract` are available for later, carefully scoped enrichment. They are not automatically querying AbuseIPDB, GreyNoise, VirusTotal, RIPEstat or a hidden service. If the group adds an enrichment step, document the exact endpoint, purpose, time, rate limit, response fields and key handling.

## Project tree

```text
Blocklist_Danish_Project_Package/
├── .vscode/
│   ├── extensions.json       # recommended VS Code extensions
│   ├── settings.json         # project interpreter and file settings
│   └── tasks.json            # clickable VS Code tasks for the main commands
├── data/
│   ├── raw/                  # immutable downloaded snapshots
│   ├── normalized/           # observations.csv created by the normalizer
│   ├── danish_evidence_template.csv
│   ├── danish_prefixes_template.csv
│   └── README.md             # data dictionary and evidence rules
├── figures/                  # diagrams used in the documents
├── logs/                     # collection log and parser notes
├── report/                   # Word reports and report framework
├── results/                 # cumulative analysis CSV files and generated PNG figures
├── run_records/             # one timestamped audit folder per complete run
├── comparisons/             # independent day-to-day comparison folders
├── archives/                # optional timestamped backup ZIPs
├── scripts/
│   ├── collect_snapshots.sh
│   ├── normalize_snapshot.py
│   ├── analyze_blocklists.py
│   ├── compare_snapshots.py
│   ├── run_daily_pipeline.py
│   ├── validate_project.py
│   ├── archive_project.py
│   ├── project_menu.py
│   └── classify_danish.py
├── tests/                    # small regression tests
├── build_report.py           # main academic report builder
├── make_*.py                 # builders for the supporting Word guides
├── requirements.txt          # Python dependencies
├── README.md                 # complete command runbook
├── SUMMARY_AR.md             # fast Arabic explanation
└── CODE_STRUCTURE_README.md  # this code explanation
```

## `scripts/collect_snapshots.sh`

This is the first stage. It is a Bash program rather than a Python program because its main task is downloading files and recording shell-level metadata.

Important variables:

- `ROOT_DIR` finds the project root even when the command is started from another directory.
- `STAMP`, `DAY` and `RETRIEVED_AT` create UTC-based names and timestamps.
- `RUN_ID` creates a unique identifier so repeated executions do not overwrite raw files.
- `RAW_DIR` is the dated directory under `data/raw/`.
- `LOG_FILE` is `logs/collection_log.csv`.
- `RUN_RECORD_DIR` and `RUN_COLLECTION_LOG` keep a per-run collection log under `run_records/`.
- `USER_AGENT` identifies the study and its contact address.
- `FIREHOL_URL`, `SPAMHAUS_URL` and `BLOCKLIST_DE_URL` hold the public feed URLs.
- `FETCH_URLHAUS` and `URLHAUS_URL` keep the optional URLhaus route disabled unless the group deliberately enables it.

Functions:

- `sha256_file`: calculates a file fingerprint with `sha256sum` or macOS `shasum`.
- `file_bytes`: reads the file size in a Linux-compatible or macOS-compatible way.
- `csv_field`: quotes values before writing a safe CSV log row.
- `download_feed`: downloads one URL, retries temporary failures, records status/bytes/hash/path in both the global and per-run logs, and prints a short result.

The three final `download_feed` calls are the actual collection actions. A failed request is logged; it is not silently replaced by a different file.

## `scripts/normalize_snapshot.py`

This is the second stage. It is a Python command-line program. Run it with `--raw-dir`, `--out` and `--errors`.

The `FIELDS` list defines the common output schema:

- `snapshot_id`, `source_name`, `retrieved_at_utc`, `source_path` and `sha256` preserve provenance.
- `indicator_type` distinguishes `ip`, `cidr`, `domain` and `url`.
- `indicator` is the canonical value used for comparison.
- `source_value` keeps the value as supplied by the provider.
- `reason` and `provider_timestamp` preserve optional provider fields.
- `country_class` starts as `Unknown` until Member 4 supplies evidence.
- `first_seen`, `last_seen` and `status` leave space for later derived or provider information.
- `notes` stores a line number or other parsing detail.

Functions:

- `sha256(path)`: reads the raw file in blocks and returns its SHA-256 digest.
- `timestamp_from_name(path)`: extracts the UTC timestamp from a collector filename; if it is absent, it uses the file modification time.
- `snapshot_id(path, retrieved_at)`: creates a stable snapshot identifier.
- `canonical_ip_or_cidr(value)`: uses `ipaddress` to validate and canonicalize an IP address or network range.
- `row(...)`: creates a complete output row with safe defaults, including `country_class=Unknown` and `status=listed`.
- `base_meta(...)`: prepares the provenance fields shared by every row in one raw file.
- `parse_firehol(...)`: removes comments and reads IP/CIDR entries from a FireHOL netset.
- `parse_blocklist_de(...)`: removes comments and reads IP/CIDR entries from the blocklist.de text file.
- `json_value(...)`: safely retrieves the first available value from several possible JSON field names.
- `parse_spamhaus(...)`: supports a JSON object, a list, or newline-delimited JSON and extracts IP/CIDR values plus optional metadata.
- `domain_from_url(...)`: extracts a lower-case hostname from a URL.
- `parse_urlhaus(...)`: supports the optional URLhaus CSV-style feed and preserves URL/domain information.
- `parse_file(...)`: chooses the correct parser by filename.
- `main()`: reads every raw file, collects parser notes, writes the normalized CSV and prints row counts.

The error file containing only `path,error` means the parser recorded zero notes. It does not mean that the feeds are proof of maliciousness; it means the file shapes were understood without parser warnings.

## `scripts/compare_snapshots.py`

This module is deliberately separate from `scripts/analyze_blocklists.py`. It reads the normalized cumulative CSV and writes only under `comparisons/`. It never changes `results/`, so a comparison can be inspected, deleted or regenerated without changing the main analysis outputs.

The selection rule is important. For each source and each selected calendar day, the module selects the latest normalized snapshot. If a source was collected twice on the same day, those runs remain in the raw evidence, but the second run is not silently treated as a new day.

If a source is missing on either selected day, the comparison marks that source as `missing_previous_snapshot` or `missing_current_snapshot` and writes `NA` for the change counts. This prevents a failed download or missing coverage from being misreported as indicator removals.

Functions:

- `snapshot_day(row)`: validates the UTC calendar date used for comparison.
- `indicator_key(row)`: keeps indicator type and canonical value together.
- `latest_snapshot(rows, source, day)`: selects one latest source/day snapshot and keeps its metadata.
- `make_status(...)`: records why a comparison is not ready or could not be made.
- `make_figure(...)`: creates the independent additions/removals comparison figure.
- `compare(...)`: creates the source summary, individual changes, snapshot index, notes and comparison manifest.
- `main()`: accepts the normalized input, comparison root, optional dates and run ID from the command line.

The comparison output includes `source_summary.csv`, `indicator_changes.csv`, one `<source>_changes.csv` file for each source, `snapshot_index.csv`, `comparison_manifest.json`, `comparison_notes.txt` and `changes_by_source.png`.

## `scripts/run_daily_pipeline.py`

This is the normal entry point for Member 3’s daily operation. It uses the current Python interpreter to run collection, normalization and cumulative analysis, then archives the analysis and calls the separate comparison module.

The runner creates `run_records/<run-id>/` before any command starts. It writes:

- `run_manifest.json`: machine-readable run status, UTC start/end times, commands, exit codes, hashes, counts and output paths;
- `run_events.csv`: timestamped lifecycle events;
- `step_*.stdout.log` and `step_*.stderr.log`: captured command output;
- `collection.csv`: the collector’s per-run provider log;
- `normalization_errors.csv`: parser notes copied for this run;
- `analysis/`: a copy of the cumulative results at that point;
- `run_summary.md`: a short handover for the group.

The `--skip-collection` option reruns normalization, analysis and comparison from existing raw snapshots. It is useful after a parser correction. It creates a new run record and does not edit raw files.

After comparison, the runner calls `scripts/validate_project.py`. The checklist result is saved as `validation_report.json` inside the same run record. A warning is expected while the study has fewer than 30 dates or while a comparison is not ready; a failure means a required file, hash, schema or archive check needs attention.

## `scripts/validate_project.py`

This is a local quality gate. It never downloads a feed and never guesses missing values. It checks required project files, Python and Bash syntax, the collection log, raw-file byte counts and hashes, the normalized schema, analysis outputs, run manifests, comparison manifests and report files. It prints `[PASS]`, `[WARN]` and `[FAIL]` lines and can save the same checklist as JSON with `--json-out`.

Use it before handing data to another group member:

```bash
python scripts/validate_project.py
python scripts/validate_project.py --run-id RUN_ID --json-out run_records/RUN_ID/validation_report_manual.json
```

The validator treats incomplete historical coverage as a warning, not as a fabricated result. A missing source snapshot in a two-date comparison remains `NA` and is not counted as a list removal.

## `scripts/archive_project.py`

This optional backup tool creates a new ZIP under `archives/`. It includes source code, documentation, raw snapshots, normalized data, results, logs, run records and comparisons. It excludes `.venv`, caches, old ZIP files and the archive folder itself, so repeated backups do not include one another. The ZIP contains `archive_manifest.json` with UTC creation time, file sizes and SHA-256 hashes.

## `scripts/project_menu.py`

This is the beginner entry point. Run `python scripts/project_menu.py` from the project root. It shows local and UTC time, then offers numbered choices:

- `1`: complete daily collection and processing;
- `2`: replay saved raw files without network collection;
- `3` and `4`: display today’s actual result or collection log;
- `5`: inspect a chosen UTC date;
- `6`: run the validation checklist;
- `7`: compare today with yesterday;
- `8`: compare two chosen dates;
- `9`: inspect an archived run record;
- `10`: create a timestamped backup ZIP;
- `11`: show project status.

Only option 1 makes network requests. Options 3–11 read saved files or create independent local outputs. The menu uses UTC as the canonical research date and shows the Mac local time only as an orientation aid; this avoids date conflicts between group members.

## `scripts/analyze_blocklists.py`

This is the third stage. It only reads the normalized CSV; it does not make new network requests.

Functions:

- `read_rows(path)`: loads CSV rows as dictionaries.
- `write_rows(path, fields, rows)`: writes analysis tables with stable headers.
- `source_day(row)`: uses the first ten characters of the UTC timestamp as the collection day.
- `observation_key(row)`: returns `(indicator_type, indicator)`, keeping an IP separate from a CIDR, domain or URL.
- `make_daily_summary(rows)`: counts unique indicators and raw rows per source/day. From the second successful day onward, it calculates additions and removals compared with the previous successful snapshot.
- `make_persistence(rows)`: records first seen, last seen, number of snapshots present, persistence ratio and right-censoring for each source/type/indicator.
- `make_overlap(rows)`: compares exact canonical values of the same indicator type and calculates intersection, union and Jaccard similarity.
- `make_figures(daily, overlap, out_dir)`: produces the unique-indicator trend, additions/removals trend and overlap chart when there is enough data.
- `main()`: connects the functions, writes `daily_summary.csv`, `persistence.csv`, `overlap.csv` and the PNG figures.

The current one-date baseline produces meaningful counts and a first overlap comparison, but it cannot support a final 30-day persistence or turnover conclusion. That is why collection continues daily.

## `scripts/classify_danish.py`

This is the fourth stage. It reads the normalized observations plus two local evidence files prepared by Member 4. It does not query a geolocation API by itself.

Functions:

- `read_csv(path)`: reads evidence rows.
- `parse_network(value)`: validates an IP or network prefix.
- `overlaps(indicator, prefix)`: checks whether an indicator is inside or overlaps a documented prefix.
- `main()`: combines evidence signals and writes `results/danish_classification.csv`.

The four labels are deliberately cautious:

- `DK-supported`: at least two independent, timestamped signals support Denmark.
- `DK-weak`: one signal or an indirect signal supports Denmark.
- `Conflicting`: Danish and non-Danish signals disagree.
- `Unknown`: no reliable country evidence is available.

These labels describe the evidence for Danish association. They do not describe criminality.

## `build_report.py` and supporting builders

`build_report.py` creates the academic Word report. Its `ReportBuilder` class manages document configuration and reusable operations. The main methods are `__init__`, `_configure`, `heading`, `paragraph`, `table`, `figure`, `page_break` and `save`. The section functions `add_cover`, `add_summary_and_preface`, `add_introduction`, `add_context`, `add_literature`, `add_methodology`, `add_findings`, `add_discussion`, `add_conclusion`, `add_references`, `add_index` and `add_appendices` add the report content in order.

The document helper `make_member_3_4_guide.py` contains the reusable `Guide` class. It also creates the pipeline diagram and implements internal bookmarks, clickable table-of-contents links, tables, captions, code blocks and page fields. The other `make_*.py` files use that helper to create the command runbook, supervisor plan, member guide and colleague explainer.

There are no custom classes in the data-pipeline scripts. They are intentionally small command-line modules with functions. The only project classes are document-building helpers; this makes the data logic easy to call from a terminal and easy to test.

## How the six members depend on one another

Member 3 must create reliable, dated snapshots and a normalized file before Member 5 can claim multi-day trends. Member 4 can begin reading provider documentation immediately, but final Danish classification waits for the normalized candidate set. Member 5 can prepare chart templates immediately, but final chart values wait for more collection days and Member 4’s evidence. Member 6 can draft policy and ethics text early, but the final discussion and conclusion wait for verified findings. Member 1 integrates all parts after each member has supplied reviewed material.

This is a controlled sequence rather than six disconnected assignments:

```text
Member 3: raw snapshots -> normalized observations
                         -> Member 4: Danish evidence and labels
                         -> Member 5: statistics and figures
                         -> Member 6: discussion and conclusion
Member 1 + Member 2: report structure and literature support throughout
```

## Useful code checks

Run these before committing or sending the folder to another member:

```bash
# Check the Bash collector without downloading anything.
bash -n scripts/collect_snapshots.sh

# Compile Python files without running the collection or analysis.
python -m py_compile scripts/normalize_snapshot.py scripts/analyze_blocklists.py scripts/compare_snapshots.py scripts/run_daily_pipeline.py scripts/classify_danish.py build_report.py

# Run the repository tests if the dependencies are installed.
python -m unittest discover -s tests -v
```

If a command fails, copy the complete command and error into the group log. Do not delete raw files to make a later command pass; fix the parser or document the failed snapshot instead.
