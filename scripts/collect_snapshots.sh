#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="${BLOCKLIST_RUN_ID:-${DEFAULT_STAMP}_pid$$}"
STAMP="$RUN_ID"
DAY="$(date -u +%Y-%m-%d)"
RETRIEVED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RAW_DIR="$ROOT_DIR/data/raw/$DAY"
LOG_DIR="$ROOT_DIR/logs"
LOG_FILE="$LOG_DIR/collection_log.csv"
RUN_RECORD_DIR="$ROOT_DIR/run_records/$RUN_ID"
RUN_COLLECTION_LOG="$RUN_RECORD_DIR/collection.csv"
USER_AGENT="${BLOCKLIST_USER_AGENT:-AAU-blocklist-study/0.1 contact: replace-with-group-email}"

FIREHOL_URL="${FIREHOL_URL:-https://raw.githubusercontent.com/firehol/blocklist-ipsets/master/firehol_level2.netset}"
SPAMHAUS_URL="${SPAMHAUS_URL:-https://www.spamhaus.org/drop/drop_v4.json}"
BLOCKLIST_DE_URL="${BLOCKLIST_DE_URL:-https://lists.blocklist.de/lists/all.txt}"
FETCH_URLHAUS="${FETCH_URLHAUS:-0}"
URLHAUS_URL="${URLHAUS_URL:-}"
URLHAUS_AUTH_KEY="${URLHAUS_AUTH_KEY:-}"

mkdir -p "$RAW_DIR" "$LOG_DIR" "$RUN_RECORD_DIR"

if [[ ! -f "$LOG_FILE" ]]; then
  printf '%s\n' 'retrieved_at_utc,source,url,http_status,bytes,sha256,path,status,notes' > "$LOG_FILE"
fi

if [[ ! -f "$RUN_COLLECTION_LOG" ]]; then
  printf '%s\n' 'retrieved_at_utc,source,url,http_status,bytes,sha256,path,status,notes' > "$RUN_COLLECTION_LOG"
fi

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

file_bytes() {
  if stat -c '%s' "$1" >/dev/null 2>&1; then
    stat -c '%s' "$1"
  else
    stat -f '%z' "$1"
  fi
}

csv_field() {
  local value="$1"
  value="${value//\"/\"\"}"
  printf '"%s"' "$value"
}

download_feed() {
  local source="$1"
  local url="$2"
  local filename="$3"
  local extra_header="${4:-}"
  local output="$RAW_DIR/${source}_${STAMP}_${filename}"
  local http_status='curl_failed'
  local bytes='0'
  local digest=''
  local state='failed'
  local notes=''

  # A run ID makes repeated executions safe. If a caller deliberately reuses
  # a run ID, do not overwrite an earlier raw response.
  local retry=0
  while [[ -e "$output" ]]; do
    retry=$((retry + 1))
    output="$RAW_DIR/${source}_${STAMP}_retry${retry}_${filename}"
  done

  if [[ -z "$url" ]]; then
    notes='URL not configured'
  elif [[ -n "$extra_header" ]]; then
    if http_status="$(curl -fL --silent --show-error --retry 3 --retry-delay 5 --connect-timeout 20 --max-time 120 -A "$USER_AGENT" -H "$extra_header" -w '%{http_code}' -o "$output" "$url")"; then
      state='ok'
    else
      notes='download failed; inspect provider terms and network access'
    fi
  elif http_status="$(curl -fL --silent --show-error --retry 3 --retry-delay 5 --connect-timeout 20 --max-time 120 -A "$USER_AGENT" -w '%{http_code}' -o "$output" "$url")"; then
    state='ok'
  else
    notes='download failed; inspect provider terms and network access'
  fi

  if [[ -f "$output" ]]; then
    bytes="$(file_bytes "$output")"
    digest="$(sha256_file "$output")"
    if [[ "$state" != 'ok' ]]; then
      notes="${notes:-partial or failed response was saved for inspection}"
    fi
  else
    output=''
  fi

  local record
  record="$({
    csv_field "$RETRIEVED_AT"; printf ','
    csv_field "$source"; printf ','
    csv_field "$url"; printf ','
    csv_field "$http_status"; printf ','
    csv_field "$bytes"; printf ','
    csv_field "$digest"; printf ','
    csv_field "$output"; printf ','
    csv_field "$state"; printf ','
    csv_field "$notes"; printf '\n'
  })"
  printf '%s\n' "$record" >> "$LOG_FILE"
  printf '%s\n' "$record" >> "$RUN_COLLECTION_LOG"

  printf '%s: %s (%s bytes) [run %s]\n' "$source" "$state" "$bytes" "$RUN_ID"
}

download_feed 'firehol' "$FIREHOL_URL" 'level2.netset'
download_feed 'spamhaus' "$SPAMHAUS_URL" 'drop_v4.json'
download_feed 'blocklist_de' "$BLOCKLIST_DE_URL" 'all.txt'

if [[ "$FETCH_URLHAUS" == '1' ]]; then
  if [[ -z "$URLHAUS_URL" ]]; then
    printf '%s\n' 'URLhaus was requested but URLHAUS_URL is empty; no URLhaus request was made.' >&2
  elif [[ -n "$URLHAUS_AUTH_KEY" ]]; then
    download_feed 'urlhaus' "$URLHAUS_URL" 'recent.csv' "Auth-Key: $URLHAUS_AUTH_KEY"
  else
    download_feed 'urlhaus' "$URLHAUS_URL" 'recent.csv'
  fi
else
  printf '%s\n' 'URLhaus is disabled. Set FETCH_URLHAUS=1 and URLHAUS_URL after checking its current access route and terms.'
fi
