#!/usr/bin/env bash
# Start the project-owned Ubuntu SSH lab container.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "ERROR: .env missing. Copy .env.example to .env and set lab credentials." >&2
  exit 1
fi

mkdir -p data/raw/auth
touch data/raw/auth/auth.log

echo "Starting ubuntu-test-server (localhost SSH lab only)..."
docker compose up -d --build
docker compose ps
echo "Auth log (host): ${ROOT}/data/raw/auth/auth.log"
