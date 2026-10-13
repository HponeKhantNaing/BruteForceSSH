#!/usr/bin/env bash
# Stop the project-owned Ubuntu SSH lab container.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Stopping ubuntu-test-server..."
docker compose stop ubuntu-test-server
docker compose ps
echo "Stopped. Host auth log preserved at data/raw/auth/auth.log (unless you reset it)."
