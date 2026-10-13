#!/usr/bin/env bash
# Thin wrapper for P2 normal authentication log collection (localhost lab only).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "ERROR: .env missing. Copy .env.example to .env first." >&2
  exit 1
fi

exec python3 scripts/p2_collect_normal.py "$@"
