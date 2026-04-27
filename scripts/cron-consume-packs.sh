#!/usr/bin/env bash
# Consume scout packs and feed them to advocate.
#
# Run by launchd 3× daily, ~1 hour after scout (10/16/22 if scout runs at 9/15/21).
# - Pull the scout-packs repo (read-only mirror)
# - Pull the advocate-outputs repo (used as the dedup source of truth)
# - Find today's .md packs that haven't already been processed (by source_pack_id)
# - POST each unprocessed pack to advocate's API
#
# Required env (set in launchd plist or shell wrapper):
#   ADVOCATE_API_BASE        e.g. http://localhost:8000
#   SCOUT_PACKS_REPO_DIR     e.g. ~/Projects/llmx-scout-packs
#   ADVOCATE_OUTPUTS_REPO_DIR e.g. ~/Projects/llmx-advocate-outputs
#
# Optional:
#   PACK_DATE                Override which day's packs to scan (YYYY-MM-DD).
#                            Default: today in local time.
#   DRY_RUN=1                Print actions without POSTing.

set -euo pipefail

: "${ADVOCATE_API_BASE:?ADVOCATE_API_BASE is required}"
: "${SCOUT_PACKS_REPO_DIR:?SCOUT_PACKS_REPO_DIR is required}"
: "${ADVOCATE_OUTPUTS_REPO_DIR:?ADVOCATE_OUTPUTS_REPO_DIR is required}"

PACK_DATE="${PACK_DATE:-$(date +%Y-%m-%d)}"
DRY_RUN="${DRY_RUN:-0}"

log() {
  printf '[%s] %s\n' "$(date -Iseconds)" "$*"
}

# 1. Pull both repos to latest.
log "pulling scout-packs..."
git -C "$SCOUT_PACKS_REPO_DIR" pull --ff-only --quiet || {
  log "WARN: scout-packs pull failed; continuing with local copy"
}

log "pulling advocate-outputs..."
git -C "$ADVOCATE_OUTPUTS_REPO_DIR" pull --ff-only --quiet || {
  log "WARN: advocate-outputs pull failed; continuing with local copy"
}

# 2. Build the set of already-consumed pack_ids from outputs/**/task.json.
#    We treat the outputs repo itself as the dedup ledger — survives across
#    machines, no separate state file to lose.
consumed_ids_file=$(mktemp)
trap 'rm -f "$consumed_ids_file"' EXIT

find "$ADVOCATE_OUTPUTS_REPO_DIR" -name task.json -type f 2>/dev/null \
  | while read -r f; do
      python3 -c "import json,sys; d=json.load(open(sys.argv[1])); pid=d.get('source_pack_id'); print(pid) if pid else None" "$f" 2>/dev/null || true
    done \
  | sort -u > "$consumed_ids_file"

consumed_count=$(wc -l < "$consumed_ids_file" | tr -d ' ')
log "found $consumed_count already-consumed pack(s)"

# 3. Walk today's pack directory and POST anything new.
packs_dir="$SCOUT_PACKS_REPO_DIR/packs/$PACK_DATE"
if [[ ! -d "$packs_dir" ]]; then
  log "no packs directory for $PACK_DATE — nothing to do"
  exit 0
fi

posted=0
skipped=0
failed=0

for pack_file in "$packs_dir"/*.md; do
  [[ -f "$pack_file" ]] || continue
  # Skip the .fulltext.md auxiliary files that scout writes alongside long packs.
  case "$pack_file" in
    *.fulltext.md) continue ;;
  esac

  # Extract pack_id from frontmatter (cheap awk parse — first occurrence wins).
  pack_id=$(awk '/^---$/{c++; next} c==1 && /^pack_id:/ {gsub(/[" ]/, "", $2); print $2; exit}' "$pack_file")
  if [[ -z "$pack_id" ]]; then
    log "WARN: $pack_file has no pack_id — skipping"
    continue
  fi

  if grep -qx "$pack_id" "$consumed_ids_file"; then
    skipped=$((skipped + 1))
    continue
  fi

  pack_basename=$(basename "$pack_file" .md)
  title="[scout] $pack_basename"
  log "POSTing pack_id=$pack_id ($pack_basename)..."

  if [[ "$DRY_RUN" == "1" ]]; then
    log "  DRY_RUN: would POST to $ADVOCATE_API_BASE/tasks"
    posted=$((posted + 1))
    continue
  fi

  # Build the request body via python so we don't have to escape the markdown.
  body=$(python3 -c "
import json, sys
content = open(sys.argv[1]).read()
print(json.dumps({
    'title': sys.argv[2],
    'source': {'pack_path': None, 'pack_content': content},
    'config': None,
    'run_async': True,
}))
" "$pack_file" "$title")

  http_code=$(curl -s -o /tmp/cron-consume-resp.txt -w '%{http_code}' \
    -X POST "$ADVOCATE_API_BASE/tasks" \
    -H 'Content-Type: application/json' \
    --data-binary "$body" || echo 000)

  if [[ "$http_code" == "200" ]] || [[ "$http_code" == "201" ]]; then
    posted=$((posted + 1))
    log "  ok ($http_code)"
  else
    failed=$((failed + 1))
    log "  FAIL ($http_code): $(head -c 200 /tmp/cron-consume-resp.txt)"
  fi
done

log "done — posted=$posted skipped=$skipped failed=$failed"
exit $((failed > 0 ? 1 : 0))
