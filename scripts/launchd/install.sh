#!/usr/bin/env bash
# Install advocate's two launchd jobs:
#   - com.llmxfactors.advocate.consume (10:05 / 16:05 / 22:05)
#   - com.llmxfactors.advocate.push (every hour at :30)
#
# Run from the repo root:
#   bash scripts/launchd/install.sh \
#     --scout-packs ~/Projects/llmx-scout-packs \
#     --outputs-repo ~/Projects/llmx-advocate-outputs \
#     [--api-base http://localhost:8000]

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCOUT_PACKS=""
OUTPUTS_REPO=""
API_BASE="http://localhost:8000"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scout-packs) SCOUT_PACKS="$2"; shift 2 ;;
    --outputs-repo) OUTPUTS_REPO="$2"; shift 2 ;;
    --api-base) API_BASE="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,11p' "${BASH_SOURCE[0]}" | sed 's/^# *//'
      exit 0 ;;
    *) echo "unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$SCOUT_PACKS" || -z "$OUTPUTS_REPO" ]]; then
  echo "Error: --scout-packs and --outputs-repo are required."
  exit 1
fi

# Resolve to absolute paths so the plists are launchd-friendly.
SCOUT_PACKS="$(cd "$SCOUT_PACKS" && pwd)"
OUTPUTS_REPO="$(cd "$OUTPUTS_REPO" && pwd)"
OUTPUTS_SRC="$PROJECT_DIR/outputs"

mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$OUTPUTS_SRC"  # docker-compose mounts this; create empty if absent

LAUNCHD_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$LAUNCHD_DIR"

render() {
  local template="$1" output="$2"
  sed \
    -e "s|__PROJECT_DIR__|$PROJECT_DIR|g" \
    -e "s|__SCOUT_PACKS_REPO_DIR__|$SCOUT_PACKS|g" \
    -e "s|__ADVOCATE_OUTPUTS_REPO_DIR__|$OUTPUTS_REPO|g" \
    -e "s|__OUTPUTS_SRC_DIR__|$OUTPUTS_SRC|g" \
    -e "s|__ADVOCATE_API_BASE__|$API_BASE|g" \
    "$template" > "$output"
}

for label in consume push; do
  template="$PROJECT_DIR/scripts/launchd/com.llmxfactors.advocate.$label.plist.template"
  target="$LAUNCHD_DIR/com.llmxfactors.advocate.$label.plist"

  echo "rendering $template → $target"
  render "$template" "$target"

  # Reload (unload first in case it's already there).
  launchctl unload "$target" 2>/dev/null || true
  launchctl load "$target"
  echo "loaded com.llmxfactors.advocate.$label"
done

echo
echo "Installed. Verify with:"
echo "  launchctl list | grep advocate"
echo
echo "Manual trigger for testing (consume):"
echo "  launchctl start com.llmxfactors.advocate.consume"
echo "  tail -f $PROJECT_DIR/logs/consume.out.log"
