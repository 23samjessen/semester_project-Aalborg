# Analysis of Public Blocklists from a Danish Perspective

This directory is the working package for a six-person Aalborg University semester project. It contains a report framework, collection and normalization scripts, analysis commands, and figures. The report is intentionally complete as a research design and writing framework, but measured findings must be inserted only after the group has collected and verified its own data.

## VS Code quick start — commands with comments

Open this folder in VS Code. The project is a small command-line data pipeline: it downloads public feed files, saves the original snapshots, converts different formats into one CSV, and calculates descriptive tables and figures. It does not scan your Mac or contact the IP addresses listed in the feeds.

The commands below are written with comments so that every step has a clear purpose. Run them from the project root. The `.venv` folder is created on each computer and is intentionally not included in the ZIP.

```bash
###########################


## Check the connection:

git status
git remote -v

For future updates:

git add -A
git commit -m "  "
git push
######
## start here:

export BLOCKLIST_USER_AGENT="AAU-blocklist-study/0.1 contact: sjesse26@student.aau.dk"

python scripts/project_menu.py


# cd ~/Downloads/Blocklist_Danish_Project_Package
# python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# start the menu 
python scripts/project_menu.py

# tomorrow 
##running commands >>>>>>>>

cd "/Users/sam/Desktop/AALBOG_UNI./first_year /semester_project_##/VSC-folders/Blocklist_Danish_Project_Package 3"
source .venv/bin/activate
export BLOCKLIST_USER_AGENT="AAU-blocklist-study/0.1 contact: sjesse26@student.aau.dk"
python scripts/project_menu.py


choose 1 then RUN 
#######
The downloaded files will be saved under:

data/raw/
data/normalized/
results/
logs/
run_records/

## Display today’s summary directly in Terminal:
column -s, -t < results/daily_summary.csv

open results
logs/collection_log.csv

results/

data/raw/2026-09-16/
# for cleaner dispaly 

python -c 'import pandas as pd; d=pd.read_csv("results/daily_summary.csv"); print(d[["source","snapshot_day","unique_indicators","raw_rows"]].to_string(index=False))'



Meaning of each column
Column	Meaning
source	The blocklist provider
snapshot_day	The UTC date when the data was collected
unique_indicators	Number of different IP addresses or CIDR network ranges after duplicates were removed
raw_rows	Total records read from the downloaded file before duplicates were removed
####################

# export BLOCKLIST_USER_AGENT="AAU-blocklist-study/0.1 contact: YOUR_EMAIL"

# Go to the folder that contains README.md and scripts/.
cd /absolute/path/to/Blocklist_Danish_Project_Package

# Confirm that the terminal is in the correct project folder.
pwd
ls

# Open this project in VS Code (the `code` command must be installed in PATH).
code .

# Create an isolated Python environment for this project.
python3 -m venv .venv

# Activate the environment for the current terminal session on macOS/Linux.
source .venv/bin/activate

# Install the exact Python libraries used by the scripts.
python -m pip install -r requirements.txt

# Optional: update pip before installing or when troubleshooting installation.
python -m pip install --upgrade pip

# Verify that the terminal is using the project environment, not system Python.
which python
python --version
python -m pip check

# Give public sources a stable contact string for responsible collection.
# Replace the example address with a group-controlled address.
export BLOCKLIST_USER_AGENT='AAU-blocklist-study/0.1 contact: YOUR-GROUP-EMAIL'

# Recommended: run collection, normalization, analysis and comparison as one controlled run.
# A new run_records/<run-id>/ folder is created for this execution.
python scripts/run_daily_pipeline.py

# Beginner option: open the numbered menu instead of remembering commands.
# The menu explains each choice and checks the result after a complete run.
python scripts/project_menu.py

# Show the newest run record and its human-readable summary.
ls -td run_records/* | head -n 1
find "$(ls -td run_records/* | head -n 1)" -maxdepth 1 -type f -print | sort

# Manual component mode is available for troubleshooting individual stages.
# Do not run this collection command as well as the complete pipeline unless that is intentional.
# Original files are saved under data/raw/YYYY-MM-DD/ and collection metadata is logged.
bash scripts/collect_snapshots.sh

# Inspect the latest collection records and check for failed downloads.
column -s, -t < logs/collection_log.csv | tail -n 10

# Parse the original snapshots into one common, traceable observation table.
# The parser keeps source paths and SHA-256 hashes so every row can be audited.
python scripts/normalize_snapshot.py --raw-dir data/raw --out data/normalized/observations.csv --errors logs/normalization_errors.csv

# An empty file containing only `path,error` means no parser notes were recorded.
cat logs/normalization_errors.csv

# Preview the normalized table and confirm its columns.
head -n 3 data/normalized/observations.csv

# Show the collection dates present in the normalized data.
cut -d, -f3 data/normalized/observations.csv | cut -c1-10 | sort -u

# Calculate daily counts, persistence, source overlap and PNG figures.
python scripts/analyze_blocklists.py --input data/normalized/observations.csv --out-dir results

# Compare the latest two distinct snapshot days in a separate comparisons/ folder.
# This command never overwrites results/.
python scripts/compare_snapshots.py --input data/normalized/observations.csv --out-dir comparisons

# Run the project quality checklist. It checks real files, syntax, hashes and outputs.
# Missing data is reported as WARN or FAIL; values are never invented.
python scripts/validate_project.py

# Create an optional timestamped backup of code, data, reports, logs and archives.
# The backup excludes .venv, caches, old ZIP files and the archives folder itself.
python scripts/archive_project.py

# List independent comparison folders and status files.
find comparisons -maxdepth 3 -type f -print | sort

# Read the daily source summary.
column -s, -t < results/daily_summary.csv

# Preview persistence results and inspect exact source overlap results.
head -n 5 results/persistence.csv
cat results/overlap.csv
cat results/analysis_notes.txt

# Create editable templates for Danish evidence and prefix classification.
cp data/danish_evidence_template.csv data/danish_evidence.csv
cp data/danish_prefixes_template.csv data/danish_prefixes.csv

# Fill the two CSV files only with evidence actually retrieved and timestamped.
code data/danish_evidence.csv
code data/danish_prefixes.csv

# Apply the transparent DK-supported/DK-weak/Conflicting/Unknown labels.
# This script reads local evidence; it does not perform network lookups.
python scripts/classify_danish.py --input data/normalized/observations.csv --evidence data/danish_evidence.csv --prefixes data/danish_prefixes.csv --out results/danish_classification.csv

# Check shell and Python syntax before sharing changes with the group.
bash -n scripts/collect_snapshots.sh
python -m py_compile scripts/normalize_snapshot.py scripts/analyze_blocklists.py scripts/compare_snapshots.py scripts/run_daily_pipeline.py scripts/classify_danish.py

# Record hashes of raw files so the evidence set can be checked later.
find data/raw -type f -exec shasum -a 256 {} + | sort > logs/raw_hash_register.txt

# Rebuild the academic Word report after the group edits its content.
python build_report.py

# Leave the virtual environment when finished with this terminal session.
deactivate
```

The current collector uses direct public HTTPS feed URLs through `curl`; it does not use an authenticated API key. The enabled feeds are FireHOL Level 2, Spamhaus DROP and blocklist.de. URLhaus is deliberately disabled until the group checks its current access route and terms. AbuseIPDB, GreyNoise, VirusTotal, RIPEstat and similar services are not called by the current collector; if the group later uses one, document the endpoint, purpose, timestamp, rate limit and key handling.

For a plain-language explanation of the program, read [`CODE_STRUCTURE_README.md`](CODE_STRUCTURE_README.md). For the fast Arabic explanation, read [`SUMMARY_AR.md`](SUMMARY_AR.md). The colleague briefing is [`report/Project_Colleague_Explainer.docx`](report/Project_Colleague_Explainer.docx).

## Beginner menu and storage decision

Start the menu from the project root with:

```bash
source .venv/bin/activate
export BLOCKLIST_USER_AGENT='AAU-blocklist-study/0.1 contact: YOUR-GROUP-EMAIL'
python scripts/project_menu.py
```

The menu uses these choices:

| Choice | Meaning |
|---|---|
| 1 | Run the complete daily pipeline. It downloads public feeds, normalizes them, analyzes them, compares available dates and runs the checklist. |
| 2 | Run the processing stages again without downloading. Use this after a parser correction or when checking saved evidence. |
| 3 | Display the actual analysis rows for today’s UTC date. |
| 4 | Display today’s collection URLs, HTTP status, timestamps, file sizes, hashes and paths. |
| 5 | Enter a UTC date such as `2026-09-16` to inspect its collection log, raw folder and run records. |
| 6 | Run the validation checklist and save a JSON validation report. |
| 7 | Compare today’s UTC date with yesterday’s UTC date. The output is placed under `comparisons/` and never changes `results/`. |
| 8 | Choose any two available UTC dates for a comparison. |
| 9 | Open a saved run summary and list every archived file belonging to that run. |
| 10 | Create a timestamped backup ZIP. |
| 11 | Show the current row count, dates, run count, comparison count and result files. |

The menu displays your Mac local time for orientation, but the project uses UTC for folder names, run IDs and research dates. This is intentional: group members may have different local dates, while one canonical UTC clock prevents a collection from being placed in two different study days. A run ID such as `20260916T120000Z_run_a1b2c3d4` is the identity of one execution; the date inside it is not a claim that the study has collected 30 days.

The project does not need Docker or a database for the current research question. Append-only raw snapshots, CSV observations, manifests, event logs, hashes and per-run analysis archives are easier for students and supervisors to inspect and reproduce. Use the optional backup ZIP or a controlled shared backup location to reduce the risk of losing the folder. A database can be considered later only if the dataset becomes too large for files or the supervisor specifically requires it.

## Project question

The project studies how selected public blocklists identify, publish, update, retain and remove indicators associated with Denmark. It combines a longitudinal snapshot study with a structured analysis of provider documentation.

Use these research questions consistently:

1. How do the selected public blocklists describe and implement their listing, update, expiry and removal processes?
2. What patterns of listing, persistence, turnover and cross-list overlap are observed for Danish-related IP addresses and domains during the collection period?
3. What practical and procedural barriers affect correction or delisting of a benign owned asset?

The main unit of analysis is an indicator–source–time observation. Keep IP addresses, CIDR ranges, domains and URLs as distinct types. Do not write that an indicator is malicious merely because it occurs in one public list.

## Why this structure fits an AAU project

The report follows a problem-based, scientific project structure: introduction and problem statement; technical context; literature review; methodology; findings; discussion; conclusion; references; appendices. This matches the emphasis in the current Cyber Security curriculum and the Distributed Systems Security module on scientific methods, literature search, quantitative data collection and analysis, source criticism, citation and a structured semester-project report.

Check the group’s own study regulation and supervisor instructions before submission:

- AAU Cyber Security curriculum: <https://studieordninger.aau.dk/2026/59/6377?lang=en-GB>
- AAU Distributed Systems Security module: <https://moduler.aau.dk/course/2026-2027/ESNCYSK1P1>
- AAU general project/report rules: <https://www.mp.aau.dk/education/rules-and-regulations-eng-da>
- AAU academic writing guide: <https://doi.org/10.13140/RG.2.2.19116.97921/2>

The generated Word report uses real Heading styles and internal hyperlinks for the table of contents, list of figures, list of tables and index. If headings are renamed, regenerate the report or update the links before submitting.

## Six-person division of work

The six work packages are connected. Each member owns a package, but every member must understand the complete method and review the complete report.

| Member | Primary responsibility | Concrete output | Secondary review |
|---|---|---|---|
| 1 | Coordination and introduction | Problem statement, aim, research questions, scope, meeting log | Final coherence and oral defence plan |
| 2 | Literature review | Search log, IEEE sources, theoretical framework, gap | References and citation consistency |
| 3 | Feed collection and normalization | Collection script, raw snapshot register, parser, data dictionary | Reproducibility and raw-data integrity |
| 4 | Danish classification and enrichment | Allocation/geolocation/ASN/DNS evidence, uncertainty labels, passive enrichment | Ethics, privacy and attribution claims |
| 5 | Quantitative analysis and visualizations | Daily counts, additions/removals, persistence, Jaccard overlap, figures | Methods-to-results traceability |
| 6 | Policy, ethics, delisting and conclusion | Provider policy matrix, safe owned-asset procedure, discussion, conclusion | Threats to validity and recommendations |

Suggested chapter ownership:

- Member 1: Chapters 1 and the final report integration.
- Member 2: Chapter 3 and the reference/source register.
- Member 3: Sections 2.1–2.4 and Chapter 4 data handling.
- Member 4: Sections 2.5–2.6 and Danish classification/enrichment results.
- Member 5: Chapter 5 quantitative findings and all result figures.
- Member 6: Chapter 4 ethics/policy method, Chapter 6, Chapter 7 and delisting evidence.

Do not submit six disconnected mini-reports. Use one shared terminology list, one data dictionary, one source register and one final editorial pass.

## Folder structure

```text
blocklist_project/
├── report/
│   └── Blocklist_Danish_Project_Report_Framework.docx
├── scripts/
│   ├── collect_snapshots.sh
│   ├── normalize_snapshot.py
│   ├── analyze_blocklists.py
│   └── classify_danish.py
├── data/
│   ├── raw/          # immutable provider snapshots; do not edit
│   └── normalized/   # derived CSV files
├── figures/          # report diagrams and generated analysis figures
├── results/          # cumulative tables and figures created from normalized data
├── run_records/      # one audit folder per complete daily run
├── comparisons/      # independent day-to-day comparisons; never replaces results/
├── logs/             # global collection and parser logs
├── build_report.py
├── requirements.txt
└── README.md
```

Raw files are evidence. Never overwrite a raw snapshot. Store the UTC timestamp, exact URL, HTTP status, content type where available, byte count and SHA-256 hash.

## What is saved after each complete daily run

Use `python scripts/run_daily_pipeline.py` for normal daily operation. The command runs collection, normalization, cumulative analysis, comparison and validation in sequence. It creates a unique folder such as `run_records/20260916T120000Z_run_a1b2c3d4/`.

Each run folder contains:

- `run_manifest.json` — machine-readable record of UTC start/end times, commands, exit codes, data hashes, row counts, output files and comparison status;
- `run_events.csv` — timestamped event timeline showing when each step started, finished and archived its outputs;
- `collection.csv` — provider responses collected during this run, including URL, HTTP status, byte count, SHA-256, path and status;
- `step_*.stdout.log` and `step_*.stderr.log` — exact program output for troubleshooting;
- `normalization_errors.csv` — a copy of parser notes for this run;
- `analysis/` — timestamped copies of the cumulative `results/` files produced at the end of this run;
- `validation_report.json` — the PASS/WARN/FAIL checklist produced after the pipeline;
- `run_summary.md` — a short human-readable handover.

The raw provider files remain in `data/raw/YYYY-MM-DD/`. The normalized cumulative table remains in `data/normalized/`, and cumulative outputs remain in `results/`; these are regenerated from the raw evidence. The comparison script writes only to `comparisons/`.

On the first successful collection day, the comparison status is `not_ready` because one distinct day is not enough. On the next distinct day, the program compares the latest snapshot for each source on the two selected days. A second run on the same calendar day is not silently counted as a new study day.

If one provider has no successful snapshot on one of the selected days, that provider is marked as missing in `source_summary.csv`. Its indicators are not falsely counted as removals; the group must report the missing coverage and avoid treating it as a real list change.

Each comparison folder contains:

- `comparison_manifest.json` — selected dates, input hash, selection rule and output hashes;
- `snapshot_index.csv` — exact previous/current snapshot IDs, timestamps, paths and hashes;
- `source_summary.csv` — counts, additions, removals, unchanged indicators and percentage change by source and indicator type;
- `indicator_changes.csv` — individual added/removed canonical indicators;
- one `<source>_changes.csv` file per provider for source-specific checking;
- `comparison_notes.txt` and `changes_by_source.png`.

If a comparison is not yet possible, `comparisons/status_<run-id>.json` records the reason without touching `results/`.

## Exact workflow

### 1. Create the environment

Run these commands from the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate with:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. Freeze the study design before collection

Before Day 1, the group must agree on:

- the exact feeds and URLs;
- the UTC collection time and cadence;
- the start and end dates;
- what counts as a successful snapshot;
- the Danish classification rule;
- which enrichment services are allowed and how often they may be queried;
- who reviews each raw file and policy capture.

Record these decisions in Appendix B and the method log. A sensible baseline is one snapshot per day for 30 consecutive days. Do not download Spamhaus more often than its documented limit; a daily snapshot is sufficient for this project. Respect every provider’s terms, authentication requirements and fair-use limits.

### 3. Run the complete daily pipeline

After the study design is frozen and the user agent is configured, run:

```bash
python scripts/run_daily_pipeline.py
```

This is the normal command to use once per collection day. It creates the timestamped run record described above. If the command reports `comparison_status=not_ready`, continue collecting on the next distinct day. If it reports `comparison_status=created`, inspect the comparison folder named in the output and send its `run_summary.md` to the group.

To rerun normalization and analysis after correcting a parser or documentation issue without downloading again:

```bash
python scripts/run_daily_pipeline.py --skip-collection
```

Use a new run folder for every rerun. Never edit the raw snapshot files.

### 4. Collect a safe baseline snapshot manually

Replace the contact string with a group-controlled address, then run:

```bash
export BLOCKLIST_USER_AGENT='AAU-blocklist-study/0.1 contact: group@example.org'
bash scripts/collect_snapshots.sh
```

The default script retrieves:

- FireHOL Level 2 as a documented aggregated IP/CIDR feed;
- Spamhaus DROP IPv4 JSON;
- blocklist.de `all.txt` as a short-retention reported-attack feed.

URLhaus is optional because the correct URLhaus dataset and access method must be selected from the official documentation. To enable an explicitly approved recent-URL feed, set its URL and run:

```bash
export FETCH_URLHAUS=1
export URLHAUS_URL='https://urlhaus.abuse.ch/downloads/csv_recent/'
bash scripts/collect_snapshots.sh
```

The script records failures rather than silently replacing a missing snapshot. Review the provider’s current feed page and terms before enabling it.

Official source pages:

- FireHOL lists: <https://iplists.firehol.org/> and <https://github.com/firehol/blocklist-ipsets/>
- Spamhaus DROP: <https://www.spamhaus.org/blocklists/do-not-route-or-peer/>
- blocklist.de export: <https://www.blocklist.de/en/export.html>
- URLhaus API and feeds: <https://urlhaus.abuse.ch/api/> and <https://urlhaus.abuse.ch/feeds/>

### 5. Normalize without deleting evidence

After a successful collection run:

```bash
python scripts/normalize_snapshot.py \
  --raw-dir data/raw \
  --out data/normalized/observations.csv \
  --errors logs/normalization_errors.csv
```

The parser keeps the original file path, source value and raw-file hash. It canonicalizes IP addresses and CIDR ranges with Python’s `ipaddress` module, lower-cases domain names, and keeps URLs as URLs. If a provider format changes, record the parser change and rerun the parser from the immutable raw files.

### 6. Run descriptive analysis and figures

```bash
python scripts/analyze_blocklists.py \
  --input data/normalized/observations.csv \
  --out-dir results
```

The analysis creates:

- `daily_summary.csv` — unique indicators, additions and removals per source/day;
- `persistence.csv` — first/last observation, persistence ratio and right-censoring;
- `overlap.csv` — exact representation-level intersections, unions and Jaccard similarity;
- `daily_unique_indicators.png`;
- `daily_additions_removals.png`;
- `source_overlap.png` when comparable data exists.

These are descriptive outputs. The group must inspect missing days, parser errors, source semantics and country evidence before interpreting them.

For a direct comparison outside the complete runner, use:

```bash
python scripts/compare_snapshots.py \
  --input data/normalized/observations.csv \
  --out-dir comparisons
```

The comparison uses the latest snapshot per source on the latest two distinct dates. It stores its own manifest, snapshot index, summary, individual changes and figure under `comparisons/`; it never writes to `results/`.

To rebuild the Word framework after changing its text or structure:

```bash
python build_report.py
```

### 7. Classify Danish-related indicators

Do not infer “Danish” from a single lookup or a `.dk` suffix. Store separate evidence fields for allocation country, geolocation country, origin ASN, reverse DNS and resolved-host country. Use the following labels:

- `DK-supported`: at least two independent, timestamped signals support Denmark;
- `DK-weak`: one signal or an indirect/broad location field supports Denmark;
- `Conflicting`: country signals disagree;
- `Unknown`: reliable country evidence is unavailable.

For CIDR ranges, report whether evidence refers to the whole range or only an overlapping Danish prefix. Keep IP/CIDR comparisons separate from domain/URL comparisons.

Passive enrichment may use RIPEstat/RIR data, RDAP, DNS and permitted provider APIs. Use AbuseIPDB, GreyNoise and VirusTotal only for the small candidate set or an explicitly documented sample. Keep API keys in environment variables, never in Git or the report.

Create the evidence files from the templates and run the transparent classifier:

```bash
cp data/danish_evidence_template.csv data/danish_evidence.csv
cp data/danish_prefixes_template.csv data/danish_prefixes.csv
# Fill both CSV files with evidence actually retrieved by the group.
python scripts/classify_danish.py \
  --input data/normalized/observations.csv \
  --evidence data/danish_evidence.csv \
  --prefixes data/danish_prefixes.csv \
  --out results/danish_classification.csv
```

The script does not perform network lookups. This is deliberate: country evidence must be timestamped, attributed and reviewable. Two independent Danish signals produce `DK-supported`; one produces `DK-weak`; Danish and non-Danish signals produce `Conflicting`; no usable evidence produces `Unknown`.

### 8. Write the report with evidence discipline

Use the generated report in this order:

1. Introduction and problem statement.
2. Technical context and blocklist dissection.
3. Literature review and theoretical framework.
4. Methodology.
5. Findings.
6. Discussion and analysis.
7. Conclusion.
8. IEEE references, index and appendices.

The Findings chapter must state only what the dataset shows. The Discussion chapter explains what those observations mean in relation to the literature, the research questions and operational use. Replace every `[insert]` or `[30]` with a measured value, a deliberate statement of non-availability, or a cited evidence reference. Never invent a result to make a table look complete.

### 9. Final group checks

Before submission, check:

```bash
sha256sum data/raw/*/* 2>/dev/null | sort > logs/raw_hash_register.txt
python scripts/normalize_snapshot.py --raw-dir data/raw --out data/normalized/observations.csv --errors logs/normalization_errors.csv
python scripts/analyze_blocklists.py --input data/normalized/observations.csv --out-dir results
python scripts/compare_snapshots.py --input data/normalized/observations.csv --out-dir comparisons
```

Then verify that every finding has a table/figure/raw snapshot or policy source; every IEEE reference is cited in the body; every figure has a caption; every appendix is named in the text; and the six-person contribution log is complete.

### No-network two-day practice

The package contains a tiny documentation-only fixture so Members 3 and 5 can practise normalization and comparison without contacting a public service:

```bash
# Create a temporary practice folder outside the project evidence folders.
practice_dir=$(mktemp -d /tmp/blocklist-practice.XXXXXX)

# Normalize the two dated fixture snapshots.
python scripts/normalize_snapshot.py \
  --raw-dir tests/fixtures/raw \
  --out "$practice_dir/observations.csv" \
  --errors "$practice_dir/errors.csv"

# Compare the two fixture dates in a temporary, independent output folder.
python scripts/compare_snapshots.py \
  --input "$practice_dir/observations.csv" \
  --out-dir "$practice_dir/comparisons" \
  --run-id practice_two_days

# Read the exact counts and change rows produced by the practice.
column -s, -t < "$practice_dir/comparisons/practice_two_days/2026-09-16_vs_2026-09-17/source_summary.csv"
```

This test is safe because the fixture uses documentation-only addresses and the commands make no network request. A missing provider snapshot in the fixture is reported as missing/`NA`, not as a removal.

## Safe practice work

The project does not require generating malicious traffic, submitting false abuse reports or probing public IP addresses. Public listing is not permission to scan a host.

If the group needs a network-security practice exercise, use an isolated lab VM or a host owned by the group. Confirm the target before scanning:

```bash
export TARGET=192.168.56.101
ip route
ping -c 2 "$TARGET"
nmap -Pn -sT --top-ports 100 --reason "$TARGET"
nmap -Pn -sV --version-light "$TARGET"
```

Do not substitute an IP copied from a public blocklist for `TARGET`. Do not run brute-force tools, exploit payloads, malware, false reports or scans against third-party systems. If a provider offers a documented test entry or DNSBL test address, use it only when the provider’s instructions and the supervisor’s approval explicitly allow it; otherwise answer the delisting question through public policy evidence and a controlled owned-asset case.

## Scheduled collection

Once the baseline is reviewed, a daily cron entry can run the complete pipeline. Use an absolute path and keep the user agent configured in the account’s environment:

```cron
15 03 * * * cd /absolute/path/to/blocklist_project && BLOCKLIST_USER_AGENT='AAU-blocklist-study/0.1 contact: group@example.org' .venv/bin/python scripts/run_daily_pipeline.py >> logs/cron.log 2>&1
```

The group should still inspect `run_records/` every day. A cron job is not evidence that a successful snapshot was obtained; the run manifest and collection log must be checked.

## Citation and reporting note

Use IEEE numbered references in the report and cite the original provider documentation, RFCs and peer-reviewed work. The report includes an AAU-style preface field for the group to complete. Keep the final argument, data interpretation and wording under the group’s control, and report the collection dates, missing sources, limitations and validation results accurately.
