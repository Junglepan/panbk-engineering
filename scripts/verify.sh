#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "[verify] root: $ROOT_DIR"

if [ -d knowledge ] && [ -f scripts/build-html.py ]; then
  if command -v uv >/dev/null 2>&1; then
    echo "[verify] running: build knowledge HTML"
    uv run scripts/build-html.py
  else
    echo "[verify] skip knowledge HTML build (uv not installed)"
  fi
fi

if [ -f package.json ]; then
  echo "[verify] detected Node project"
  if npm run | rg -q "\blint\b"; then
    echo "[verify] running: npm run lint"
    npm run lint
  else
    echo "[verify] skip lint (no npm script)"
  fi

  if npm run | rg -q "\btest\b"; then
    echo "[verify] running: npm test"
    npm test
  else
    echo "[verify] skip test (no npm script)"
  fi

  if npm run | rg -q "\btypecheck\b"; then
    echo "[verify] running: npm run typecheck"
    npm run typecheck
  else
    echo "[verify] skip typecheck (no npm script)"
  fi

  echo "[verify] done"
  exit 0
fi

if [ -f Makefile ] && rg -q "^test:" Makefile; then
  echo "[verify] running: make test"
  make test
  echo "[verify] done"
  exit 0
fi

echo "[verify] no known project verifier found (package.json/Makefile)."
echo "[verify] done"
