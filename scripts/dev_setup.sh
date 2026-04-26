#!/usr/bin/env bash
# One-shot local dev bootstrap. Idempotent.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "==> Copying .env.example -> .env (please fill in API keys)"
  cp .env.example .env
fi

echo "==> Starting infrastructure (postgres / redis / minio)..."
docker compose up -d postgres redis minio

if [ ! -d .venv ]; then
  echo "==> Creating venv (Python 3.12)..."
  python3.12 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing dev dependencies..."
pip install --upgrade pip
pip install -e ".[dev]"

echo "==> Running migrations..."
alembic upgrade head || echo "[WARN] alembic upgrade failed — run after writing first migration."

echo ""
echo "Done. Next steps:"
echo "  1. Edit .env and fill in ANTHROPIC_API_KEY / OPENROUTER_API_KEY"
echo "  2. Run: source .venv/bin/activate"
echo "  3. Run: uvicorn llmx_advocate.api.main:app --reload"
