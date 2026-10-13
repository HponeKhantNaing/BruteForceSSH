#!/usr/bin/env bash
# Show status of the project-owned Ubuntu SSH lab.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== docker compose ps ==="
docker compose ps
echo
echo "=== health ==="
docker inspect --format='{{.State.Health.Status}}' ai-security-ubuntu-lab 2>/dev/null || echo "container not running"
echo
echo "=== auth log path ==="
echo "${ROOT}/data/raw/auth/auth.log"
if [[ -f data/raw/auth/auth.log ]]; then
  echo "=== auth log tail (last 5 lines) ==="
  tail -n 5 data/raw/auth/auth.log || true
fi
