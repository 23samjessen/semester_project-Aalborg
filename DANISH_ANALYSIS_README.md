# Danish blocklist analysis extension

This adds dated Danish registry evidence and analysis of **all saved observation dates** to our blocklist project. It uses the existing `data/normalized/observations.csv`. It does not collect another copy of the blocklists, change the original menu, or overwrite the original results.

The old `classify_danish.py` reads manually supplied evidence. This extension is a separate, dated method. Its `DK_FULL` label is not equivalent to the old classifier's `DK-supported` category. Do not merge those labels without explaining the different definitions.

## Start here

Run commands from the project folder. Python 3.10 or newer is required. No additional Python packages or API key are needed for this extension.

```bash
# Open the Danish analysis menu. This command itself makes no network request.
python3 scripts/danish_study.py --menu
```

| Menu | Action |
|---|---|
| 1 | Audit saved observations and cached evidence. Make a separate report of available and missing inputs. Offline. |
| 2 | Request missing dated DK registry evidence and analyse all saved dates. This is the normal first analysis. |
| 3 | Repeat the analysis using only existing evidence. Offline; creates a new run folder. |
| 4 | List generated reports with their date ranges and exact file paths. |
| 5 | Open our original project menu for blocklist collection and other existing options. |
| 0 | Exit. |

Options 1–3 ask for a start and end date. Press Enter twice to cover the available normalized observation period. Enter explicit dates to check gaps before/after that period. Dates use `YYYY-MM-DD`, in UTC.

The original menu's option 100 does not automatically include this extension. Keep this report as a separate evidence package and use its Danish tables in the final research report. No unknown version of the original menu is patched.

## All running commands

```bash
# Go to the current project directory; preserve the spaces in this path.
cd "/Users/sam/Desktop/AALBOG_UNI./first_year /semester_project_##/VSC-folders/Blocklist_Danish_Project_Package 3"

# Identify our project in requests to the public registry API.
export BLOCKLIST_USER_AGENT="AAU-blocklist-study/0.1 contact: sjesse26@student.aau.dk"

# Check Python version. The extension requires Python 3.10+.
python3 --version

# Run the included synthetic tests. These do not contact any server.
python3 tests/test_danish_study.py

# Check existing data/evidence. This generates a report but does not download anything.
python3 scripts/danish_study.py --audit

# Fetch historical DK registry evidence, then analyse all saved dates.
# This contacts RIPEstat only, not any IP found in a blocklist.
python3 scripts/danish_study.py --fetch

# Analyse a specific study window, exposing missing source/day records.
python3 scripts/danish_study.py --fetch --start 2026-09-16 --end 2026-10-08

# Repeat offline with the same cached evidence. A separate output folder is created.
python3 scripts/danish_study.py

# Show all analysis run IDs, date ranges and output folders.
python3 scripts/danish_study.py --list-runs

# Open the new menu, including access to the original program.
python3 scripts/danish_study.py --menu

# Print command options.
python3 scripts/danish_study.py --help
```

To open a report on macOS, copy its exact printed path and use `open "/full/path/to/report.html"`, or double-click `report.html` in Finder. The report opens locally in a browser. Print → Save as PDF creates a shareable copy; keep its CSV files and manifest as the research evidence.

There is no need to activate the old virtual environment for this extension. If option 5 opens an original menu that needs pandas/matplotlib, run the new menu with the project's working virtual-environment Python, after fixing/recreating that environment if it still points to the old Downloads folder. This installer does not rebuild or remove `.venv`.

## What counts as Danish?

The primary definition is **an IP address or part of a CIDR included in the dated DK resource ranges returned by RIPEstat from RIR statistics**. It is an administrative registry association. It is not a claim that an address is physically in Denmark, belongs to a Danish person, or is currently malicious.

The public endpoint is:

`https://stat.ripe.net/data/country-resource-list/data.json?resource=dk&time=YYYY-MM-DD&v4_format=prefix`

For each saved collection date, the extension requests that date's country-resource list. The response query date must match. Requests are sequential, have a timeout and bounded retries, and successful responses are cached. Existing evidence is reused without another request. If historical evidence cannot be retrieved or validated, classification stays unknown. Current country evidence is never silently substituted for a past date.

The response query is truncated to midnight by the API. Underlying RIR files can have different update times. This is a dated registry proxy, not instantaneous physical geolocation or verified historical ownership. Evidence is retrieved retrospectively: its retrieval date is recorded separately from the date requested.

| Classification | Meaning |
|---|---|
| `DK_FULL` | The whole IP/CIDR falls within the DK registry ranges. |
| `DK_PARTIAL` | Part of a larger CIDR overlaps DK ranges. The matched subranges are recorded. |
| `NO_DK_MATCH` | No match under this rule; not proof of a foreign physical location. |
| `UNKNOWN_EVIDENCE` | Dated registry evidence is unavailable. |
| `NOT_IP_IN_SCOPE` | A domain/URL cannot be classified by an IP-range rule. |

`DK_any_match = DK_full + DK_partial` counts **entries**, not individual addresses. IPv4 and IPv6 address coverage is calculated separately after merging overlapping ranges. A /24 is one entry but contains 256 addresses. It is not 256 attacks. The code uses interval arithmetic; it never expands large IPv6 networks into individual addresses.

## Where everything is saved

- Project → `data` → `danish_registry_evidence` → `YYYY-MM-DD` → timestamped response JSON and metadata JSON. These are registry evidence, not blocklist downloads.
- Project → `danish_analysis` → `UTC_RUN_ID_danish` (or `_audit`) → a complete analysis run.
- Within a run → `comparisons` → temporal comparison files.
- Installer backups, if this extension already existed: project → `extension_backups` → timestamp. Existing original program files are not replaced.

Each run has a new UTC ID and cannot overwrite another run. Original `data/raw`, `data/normalized/observations.csv`, `results`, `comparisons`, `run_records` and `scripts/project_menu.py` remain unchanged. Back up the new evidence and run folders too. Docker and a database are not required for this scale.

## Which result to read

| File inside the new run | Purpose |
|---|---|
| `report.html` | Overall explanation, charts, selected tables, limitations and links to all outputs. |
| `daily_summary.csv` | Per-date/per-source global counts, Danish full/partial matches, unknowns and deduplicated address coverage. |
| `danish_indicators.csv` | Only full/partial Danish matches, with the original indicator, matched subranges, date, source and evidence hash. |
| `classified_observations.csv` | Every selected indicator, including unknown and nonmatching entries. This may be a large file. |
| `coverage.csv` | Every expected source/day, including missing or blocked snapshots and raw-file verification status. |
| `audit_issues.csv` | Missing evidence, input errors, warnings and manual research tasks. Start here when results look unusual. |
| `snapshot_index.csv` | All normalized snapshot identities, selection flags, timestamps, raw paths and recorded hashes. |
| `evidence_index.csv` | Exact registry URLs, requested dates, retrieval dates and file hashes. |
| `comparisons/daily_comparisons.csv` | Adjacent **calendar days**: global IP/CIDR entries, full DK matches, and any DK matches. Missing days remain unknown. |
| `comparisons/daily_DK_indicator_changes.csv` | Individual DK entries added/removed between adjacent dates, with feed-change versus registry-scope-change labels. |
| `comparisons/all_date_pairs.csv` | Every pair of available normalized dates, with gap length. Do not sum changes across overlapping pairs. |
| `comparisons/first_vs_last.csv` | First versus last date of the requested window. Header-only if a boundary has no eligible data or only one date exists. |
| `comparisons/address_space_changes.csv` | Adjacent-date changes in covered DK IPv4/IPv6 addresses, independent of exact CIDR formatting. |
| `persistence.csv` | Observed days present, eligible days, first/last observation, streaks, sampled reappearance and censoring flags. |
| `overlap.csv` | Same-date pairwise exact DK entry overlap and address-space overlap. |
| `exclusive_contribution.csv` | Entries/address space supplied only by one of the selected providers. Unknown unless all expected feeds are available. |
| `fixed_registry_sensitivity.csv` | Repeats DK classification with the earliest available registry map held fixed, to examine sensitivity to registry changes. |
| `dk_indicators.svg`, `global_indicators.svg` | Charts. Missing values break the lines. SVG stays sharp in a report. |
| `validation.json` | Check status and error/warning counts. Validation is not proof of ground-truth maliciousness. |
| `run_status.json` | Whether a run completed; a `running` record without a manifest indicates an interrupted run. |
| `run_manifest.json` | Script version, source input hashes, selected period, evidence dates and generated file hashes. |

CSV files can be opened in a spreadsheet. Import indicators as text. IPv6 coverage integers can exceed spreadsheet numeric precision; retain the exact CSV string or use Python integers. Do not treat `NA` as zero.

## Snapshot selection and changes

The extension takes the **latest unambiguous normalized snapshot for each source/UTC day**. It does not combine different runs on the same day. This means its totals can differ from an older `results/daily_summary.csv` built from the union of all daily snapshots. Use the extension's own daily summary and comparisons together. `snapshot_index.csv` explains the inputs.

A newer successful collection log entry without normalized observations blocks fallback to an older snapshot. It might be an empty feed, a parsing problem, or an unprocessed download; the extension does not guess. Check that raw file and rerun the original normalizer as appropriate. Identical latest timestamps from different snapshot IDs are also treated as ambiguous. A missing raw file permits a provisional normalized-data result with a warning; a mismatched raw checksum blocks that snapshot.

For two sampled sets A and B:

- Added = B minus A; removed = A minus B; unchanged = A intersect B.
- Net change = current count minus previous count.
- Percent change = 100 × net change / previous count; undefined (`NA`) when previous count is zero.
- Jaccard overlap = intersection size / union size; undefined (`NA`) for two empty sets.

In Danish comparisons, an entry can leave the Danish group while remaining in the blocklist. `registry_scope_entered` and `registry_scope_left` separate this from feed changes. Full-only and any-match sensitivity is available through the `scope` column. Address-space changes detect cases where a CIDR was split/merged without changing the covered IP space. They can also reflect country-map changes and should be read with the fixed-registry sensitivity table.

The report flags absolute global count changes of at least 40% for review. This is an exploratory diagnostic threshold, not a statistical significance test or proof of a collection failure. A fall in counts can reflect provider updates, expiry, parser problems, feed configuration or missing data. Establish the cause from logs and provider evidence; do not guess from the graph.

## Persistence and overlap limitations

Persistence is observed presence over eligible sampled dates, not the true time an indicator stayed listed. First/last observations are censored at study boundaries and around gaps. A daily sample cannot reveal changes within the day. Reappearance is counted only when a sampled absence lies between sampled presences. Missing days alone never prove removal or reappearance. In DK scope, registration changes may affect presence.

Exact-key overlap distinguishes an IP from a CIDR. Address overlap also recognises a host covered by another list's CIDR. All range calculations merge overlaps to avoid double counting. Exclusive contribution is relative to the feeds in this analysis only. FireHOL combines upstream feeds, so agreement between sources is not automatically independent confirmation.

The extension expects FireHOL, Spamhaus DROP and blocklist.de by default. It also audits any additional sources in the observations. If the documented study design deliberately used another source set, pass it with `--sources "FireHOL,Spamhaus DROP,blocklist.de"`; do not remove a failed source merely to make coverage look complete.

## What the missing-data check can and cannot add

It can automatically request the dated DK registry evidence needed for saved observations. It can recompute consistent daily counts, all-date-pair comparisons, persistence, overlap and charts. It reports unprocessed downloads, invalid rows, missing raw files, changed hashes, gaps, absent domains and missing dated evidence.

It cannot recreate a blocklist snapshot never collected. A screenshot exported today from saved historical data is a new presentation of those data, not a historical download. It cannot automatically establish false positives, prove IP ownership/location, explain provider decisions, supply a PRISMA search procedure, or complete an authorised listing/delisting experiment. Independent reputation services remain a separate optional enrichment step with their own access terms and dated evidence.

The script checks the normalized data it receives. It cannot recover valid raw indicators silently omitted by an older parser. Compare parser notes with raw formats during the original pipeline validation.

Thirty distinct complete sampled dates is the program's planning target. The project brief asks for at least a month-long history; 30 is not a universal scientific rule. Coverage, missing days and other research tasks still need review. Use `--minimum-days` only when the project design explicitly justifies another target. A completed computation is not a completed research conclusion.

## Suggested working routine

1. Finish the original daily collection/normalization before running this extension. Avoid concurrent writers to the observations or collection log.
2. Run menu option 2. Existing registry evidence is reused; only missing dated evidence needs a request.
3. Open the printed `report.html` path and inspect `audit_issues.csv` and `coverage.csv` first.
4. Review `danish_indicators.csv` and the daily table. Separate full from partial matches in the report.
5. Use daily comparisons for changes and all-date pairs for particular intervals. Read the calendar gap before interpreting a comparison.
6. Use persistence and overlap with their stated limitations. Investigate flagged changes in the raw snapshots and logs.
7. Preserve the run manifest and evidence cache with the dataset. Record which run supplied each submitted figure/table.

## Design, testing and scope of verification

See `DANISH_ANALYSIS_STRUCTURE.md` for the file/function design. Included tests use synthetic documentation IP ranges, not research findings. They cover latest-snapshot selection, duplicates, partial CIDRs, IPv6, missing dates, zero denominators, corrupted evidence, checksum failures, unprocessed newer downloads, registry-only changes, reappearance and range overlap.

The extension was also exercised against the available archived project CSV/raw files for 2026-09-16 using a live dated RIPEstat response. This does not verify the current files on Sam's Mac. The first local run performs that audit. No current study totals are assumed from older screenshots.

Method sources:

[1] RIPE NCC, “Country Resource List,” RIPEstat API documentation. https://data.stat.ripe.net/docs/data-api/api-endpoints/country-resource-list

[2] K. Burdiek, “Country Codes in the RIPE Database,” RIPE Labs, May 17, 2023. https://labs.ripe.net/author/kjerstin-burdiek/country-codes-in-the-ripe-database/
