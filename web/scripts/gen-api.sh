#!/usr/bin/env bash
# Generate TS types from FastAPI OpenAPI schema.
# Run from repo root or web/ — auto-detects.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [[ ! -d ".venv" ]]; then
  echo "Error: .venv not found at repo root. Run 'python -m venv .venv && pip install -e .[dev]' first."
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

LLMX_DATABASE_URL="sqlite+aiosqlite:///./scratch.db" \
  python -c "from llmx_advocate.api.main import app; import json; print(json.dumps(app.openapi()))" \
  > web/openapi-snapshot.json

cd web
pnpm exec openapi-typescript ./openapi-snapshot.json -o ./src/api/schema.ts
echo "Generated web/src/api/schema.ts"
