#!/usr/bin/env bash
# Thin wrapper for P3 controlled security scenario collection (localhost lab only).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "ERROR: .env missing. Copy .env.example to .env first." >&2
  exit 1
fi

exec python3 scripts/p3_collect_security.py "$@"
