#!/usr/bin/env bash
# End-to-end smoke: start API on a sqlite db, post a real source pack,
# poll until terminal status, dump the final report.
#
# Usage:
#   scripts/run_smoke.sh                                          # uses scout-real fixture
#   scripts/run_smoke.sh path/to/pack.md                          # custom pack
#   PORT=8765 DB=/tmp/x.db scripts/run_smoke.sh                   # override defaults
#
# Requires .env populated with OPENROUTER_API_KEY (and any LLMX_DEFAULT_MODEL /
# LLMX_JUDGE_MODEL overrides). Runs the API in the foreground of a sub-shell so
# Ctrl-C cleans up properly.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACK="${1:-$ROOT/tests/fixtures/example-pack/scout-real-deepseek-v4.md}"
PORT="${PORT:-8765}"
DB="${DB:-/tmp/llmx-smoke.db}"
TIMEOUT_S="${TIMEOUT_S:-1800}"  # 30 min default

cd "$ROOT"

if [ ! -f "$PACK" ]; then
  echo "pack file not found: $PACK" >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo ".env missing — copy from .env.example and fill OPENROUTER_API_KEY" >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

rm -f "$DB"

echo "==> Starting API on :$PORT (db=$DB)..."
LLMX_DATABASE_URL="sqlite+aiosqlite:///$DB" \
  python -m uvicorn llmx_advocate.api.main:app --host 127.0.0.1 --port "$PORT" --log-level warning &
API_PID=$!

cleanup() {
  kill "$API_PID" 2>/dev/null || true
  wait "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT

# Wait for API ready.
until curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; do
  sleep 1
done
echo "==> API up. Posting task with pack: $(basename "$PACK")"

LLMX_API_BASE_URL="http://127.0.0.1:$PORT" \
  llmx task new "$PACK" >/tmp/llmx-smoke.log 2>&1 &
CLI_PID=$!

echo "==> Polling for terminal status (timeout ${TIMEOUT_S}s)..."
python - <<PY
import httpx, sys, time
deadline = time.time() + ${TIMEOUT_S}
last_runs = -1
while time.time() < deadline:
    try:
        tasks = httpx.get("http://127.0.0.1:${PORT}/tasks", timeout=10).json()
        if tasks:
            tid = tasks[0]["id"]
            info = httpx.get(f"http://127.0.0.1:${PORT}/tasks/{tid}", timeout=10).json()
            task = info["task"]
            n = len(info["runs"])
            if n != last_runs:
                last_runs = n
                if n:
                    last = info["runs"][-1]
                    qa = ""
                    if last.get("qa_result"):
                        ok = sum(1 for g in last["qa_result"]["gates"] if g["passed"])
                        total = len(last["qa_result"]["gates"])
                        qa = f" qa={ok}/{total}"
                    t = time.strftime("%H:%M:%S")
                    print(f"  [{t}] runs={n} status={task['status']} phase={task['current_phase']} last={last['phase_id']}/{last['status']}{qa}", flush=True)
            if task["status"] in ("completed", "failed"):
                print(f"TERMINAL: {task['status']}", flush=True)
                sys.exit(0 if task["status"] == "completed" else 2)
    except Exception:
        pass
    time.sleep(15)
print("TIMEOUT", flush=True)
sys.exit(3)
PY

POLL_RC=$?

echo
echo "==> Final task summary:"
LLMX_API_BASE_URL="http://127.0.0.1:$PORT" \
  llmx task list || true

echo
echo "==> CLI output:"
cat /tmp/llmx-smoke.log || true

exit $POLL_RC
