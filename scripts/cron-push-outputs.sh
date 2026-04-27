#!/usr/bin/env bash
# Push the advocate engine's export tree into the llmx-advocate-outputs repo.
#
# Designed to run on the host (not inside docker), so git credentials live in
# the user's standard SSH/HTTPS config — no secrets in containers.
#
# Suggested cadence: hourly via launchd. The engine writes to ./outputs as
# tasks finish; this script picks up whatever's accumulated since the last push.
#
# Required env:
#   OUTPUTS_SRC_DIR             host path docker mounted to /app/outputs
#                               e.g. ~/Projects/llmx-advocate-agent/outputs
#   ADVOCATE_OUTPUTS_REPO_DIR   git working copy of llmx-advocate-outputs
#
# Optional:
#   GIT_AUTHOR_NAME / GIT_AUTHOR_EMAIL — overrides the repo's default identity.
#   DRY_RUN=1 — log what would happen without committing/pushing.

set -euo pipefail

: "${OUTPUTS_SRC_DIR:?OUTPUTS_SRC_DIR is required}"
: "${ADVOCATE_OUTPUTS_REPO_DIR:?ADVOCATE_OUTPUTS_REPO_DIR is required}"

DRY_RUN="${DRY_RUN:-0}"

log() {
  printf '[%s] %s\n' "$(date -Iseconds)" "$*"
}

if [[ ! -d "$OUTPUTS_SRC_DIR" ]]; then
  log "OUTPUTS_SRC_DIR does not exist yet — nothing to push"
  exit 0
fi

if [[ ! -d "$ADVOCATE_OUTPUTS_REPO_DIR/.git" ]]; then
  log "ERROR: $ADVOCATE_OUTPUTS_REPO_DIR is not a git repo"
  exit 1
fi

# 1. Pull first so we don't push a fast-forward conflict.
log "pulling latest..."
git -C "$ADVOCATE_OUTPUTS_REPO_DIR" pull --ff-only --quiet || {
  log "WARN: pull failed; aborting to avoid divergence"
  exit 1
}

# 2. Sync the engine's output tree into the repo working copy.
#    Use rsync so we copy newly-written task dirs without disturbing the .git
#    metadata. --ignore-existing isn't right (we'd miss updated task.json on
#    a re-run); plain rsync is correct: subsequent runs of the same task will
#    overwrite, and atomic_write_text in core/export.py prevents torn files.
log "syncing $OUTPUTS_SRC_DIR → $ADVOCATE_OUTPUTS_REPO_DIR ..."
rsync -a --exclude '.git' --exclude '.tmp' \
  "$OUTPUTS_SRC_DIR"/ "$ADVOCATE_OUTPUTS_REPO_DIR"/

# 3. Stage + diff.
cd "$ADVOCATE_OUTPUTS_REPO_DIR"
git add -A

if git diff --cached --quiet; then
  log "no changes — nothing to commit"
  exit 0
fi

# 4. Build a commit message summarising the changes.
added=$(git diff --cached --name-only --diff-filter=A | wc -l | tr -d ' ')
modified=$(git diff --cached --name-only --diff-filter=M | wc -l | tr -d ' ')

# Pull task ids from any added task.json paths for a more useful subject line.
new_task_ids=$(
  git diff --cached --name-only --diff-filter=A \
    | awk -F/ '/task\.json$/ {print $(NF-1)}' \
    | sort -u \
    | head -5 \
    | paste -sd, -
)

subject="archive: $added added, $modified modified"
[[ -n "$new_task_ids" ]] && subject="$subject (${new_task_ids})"

log "commit subject: $subject"

if [[ "$DRY_RUN" == "1" ]]; then
  log "DRY_RUN: would commit + push"
  git diff --cached --stat | head -20
  exit 0
fi

# 5. Commit + push.
commit_args=()
[[ -n "${GIT_AUTHOR_NAME:-}" ]] && commit_args+=(--author "${GIT_AUTHOR_NAME} <${GIT_AUTHOR_EMAIL:-noreply@local}>")

git commit "${commit_args[@]}" -m "$subject" --quiet
log "pushing..."
git push --quiet
log "done"
