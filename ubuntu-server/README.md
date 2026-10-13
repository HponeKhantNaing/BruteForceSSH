# Ubuntu Test Server (P1 Lab)

## Purpose

This directory defines the **project-owned Ubuntu Docker SSH lab**.

It is the local authentication log source for later phases (P2+).

Scope: `localhost` / Docker private network / controlled test accounts only.

## Start

From the repository root:

```bash
cp -n .env.example .env   # if needed; edit disposable lab password
./scripts/lab_start.sh
```

Or:

```bash
docker compose up -d --build
```

## Stop

```bash
./scripts/lab_stop.sh
```

Or:

```bash
docker compose stop ubuntu-test-server
```

## Status

```bash
./scripts/lab_status.sh
```

## SSH

Connect only to the local lab:

```bash
ssh -p "${LAB_SSH_PORT:-2222}" "${LAB_SSH_USER:-testuser}@127.0.0.1"
```

Username and password come from `.env` (`LAB_SSH_USER`, `LAB_SSH_PASSWORD`).

Do **not** publish the real password in docs or commits.

Root SSH login is disabled.

## Logs

| Location | Path |
|---|---|
| Inside container | `/var/log/auth-lab/auth.log` |
| Host (P2 handoff) | `data/raw/auth/auth.log` |

OpenSSH AUTH/PAM messages are written via `rsyslog` into that file (bind-mounted).

## Reset

Preserve previous scenario (backup + truncate):

```bash
./scripts/lab_reset_logs.sh
```

Restart if needed:

```bash
docker compose restart ubuntu-test-server
```

## Safety Scope

```text
localhost/project-controlled use only
```

Do not point scanners, credential sprays, or attack tools at external hosts.
