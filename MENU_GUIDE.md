# Beginner Menu Guide

This is the easiest way to use the project in VS Code.

## Start the menu

Open Terminal in VS Code and run these commands from the folder that contains `README.md`:

```bash
source .venv/bin/activate
export BLOCKLIST_USER_AGENT='AAU-blocklist-study/0.1 contact: YOUR-GROUP-EMAIL'
python scripts/project_menu.py
```

Replace `YOUR-GROUP-EMAIL` with an address controlled by the group. The variable is sent as the contact information in the public feed request. The program does not send a private API key.

## What to choose

`1` — Run the real daily collection. Type `RUN` when asked. The program saves the public responses, normalizes them, creates analysis files, archives the result and runs the checklist.

`2` — Run again without downloading. This reuses the raw files already saved on the computer. Use it after fixing a parser or when checking the result safely.

`3` — Display the analysis for today’s UTC date.

`4` — Display today’s collection log. It shows the exact URL, UTC time, status, size, SHA-256 and raw-file path.

`5` — Enter a date such as `2026-09-16` to inspect the log, raw folder and run records for that date.

`6` — Run the validation checklist. Read every `[FAIL]` before sharing results. `[WARN]` is expected when the project has fewer than 30 dates or when the first comparison is not ready.

`7` — Compare today with yesterday. If one of the dates is unavailable, the program records that fact instead of inventing a difference.

`8` — Compare two dates selected by the user.

`9` — Open a saved run record. This is where the group can read what happened during one execution.

`10` — Make a timestamped ZIP backup. It includes the evidence and excludes the virtual environment and previous ZIP files.

`11` — Display the current project status.

`0` — Close the menu.

## Where files go

- Original provider responses: `data/raw/YYYY-MM-DD/`
- Normalized table: `data/normalized/observations.csv`
- Cumulative analysis: `results/`
- One audit folder per run: `run_records/<run-id>/`
- Independent day comparisons: `comparisons/<run-id>/`
- Optional backups: `archives/`

The raw response is evidence and is not overwritten. A run ID uses UTC, for example `20260916T120000Z_run_a1b2c3d4`. The menu shows Mac local time too, but the project uses UTC so the six members share one date definition.

## When something is missing

The menu does not fill gaps with made-up values. A missing feed, parser note, unavailable date or failed comparison is shown in the logs and validation report. Do not describe a missing source as a list removal. Fix the collection issue or report the limitation.

The current project uses public FireHOL, Spamhaus DROP and blocklist.de feeds. URLhaus is disabled. AbuseIPDB, GreyNoise, VirusTotal and RIPEstat are not called by this program.
