#!/bin/bash
# Lab SSH container entrypoint — create test user, start logging, run sshd in foreground.
set -euo pipefail

log() {
  echo "[lab-entrypoint] $*"
}

: "${LAB_SSH_USER:?LAB_SSH_USER environment variable is required}"
: "${LAB_SSH_PASSWORD:?LAB_SSH_PASSWORD environment variable is required}"

if [[ -z "${LAB_SSH_USER}" || -z "${LAB_SSH_PASSWORD}" ]]; then
  echo "ERROR: LAB_SSH_USER and LAB_SSH_PASSWORD must be non-empty" >&2
  exit 1
fi

if [[ "${LAB_SSH_USER}" == "root" ]]; then
  echo "ERROR: LAB_SSH_USER must not be root (root SSH login is disabled)" >&2
  exit 1
fi

mkdir -p /var/run/sshd /var/log/auth-lab /var/log /run/rsyslog
touch /var/log/auth-lab/auth.log
chmod 755 /var/log/auth-lab
# World-writable lab log file so rsyslog can append across bind-mount UID differences.
chmod 666 /var/log/auth-lab/auth.log || true

# Ensure host keys exist (safe if already present)
ssh-keygen -A >/dev/null

# Create disposable lab account if missing
if ! id "${LAB_SSH_USER}" >/dev/null 2>&1; then
  log "Creating lab user: ${LAB_SSH_USER}"
  useradd -m -s /bin/bash "${LAB_SSH_USER}"
else
  log "Lab user already exists: ${LAB_SSH_USER}"
fi

# Set password from environment (disposable lab credential only)
echo "${LAB_SSH_USER}:${LAB_SSH_PASSWORD}" | chpasswd

# Validate SSH daemon configuration before start
if ! /usr/sbin/sshd -t; then
  echo "ERROR: sshd configuration validation failed" >&2
  exit 1
fi
log "sshd configuration validation passed"

# Container-friendly rsyslog: disable kernel log module (fails without privileges)
if [[ -f /etc/rsyslog.conf ]]; then
  sed -i -E 's/^(\s*module\(load="imklog".*)/# \1/' /etc/rsyslog.conf || true
  sed -i -E 's/^(\$ModLoad[[:space:]]+imklog)/# \1/' /etc/rsyslog.conf || true
fi

# Start rsyslog so OpenSSH AUTH / PAM messages reach /var/log/auth-lab/auth.log
log "Starting rsyslogd"
rsyslogd
sleep 1

log "Starting sshd in foreground (lab scope: project-owned container only)"
exec /usr/sbin/sshd -D
