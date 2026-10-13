#!/usr/bin/env bash
# Safely reset host-visible lab authentication logs for a new collection scenario.
# Does NOT target any external system. Does NOT remove the container image.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

AUTH_DIR="data/raw/auth"
AUTH_LOG="${AUTH_DIR}/auth.log"

mkdir -p "${AUTH_DIR}"

if [[ -f "${AUTH_LOG}" ]]; then
  TS="$(date -u +%Y%m%dT%H%M%SZ)"
  BACKUP="${AUTH_DIR}/auth.log.bak.${TS}"
  echo "Backing up current auth log to ${BACKUP}"
  cp "${AUTH_LOG}" "${BACKUP}"
fi

# Truncate in place so the bind mount inode stays valid for a running rsyslog/sshd.
: > "${AUTH_LOG}"
chmod 666 "${AUTH_LOG}" || true

echo "Auth log reset: ${AUTH_LOG}"
echo "Preserve backups under ${AUTH_DIR}/auth.log.bak.* if you need previous scenario data."
echo "Tip: restart the lab if logging appears stuck: docker compose restart ubuntu-test-server"
