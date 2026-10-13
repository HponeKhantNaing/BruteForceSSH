# P1 — Ubuntu Docker Test Server

**Phase:** P1  
**Depends on:** P0  
**Status:** Implemented lab SSH authentication log source (see `P1_VERIFICATION.md` for runtime results)

---

## Objective

Provide a reproducible, project-owned Ubuntu Docker SSH server that:

- runs locally on the developer host,
- exposes SSH only on `127.0.0.1`,
- creates disposable lab accounts from environment variables,
- emits real OpenSSH authentication events,
- makes those events host-visible for P2+ collection.

P1 ends at the authentication log source. Collector, parser, ML, dashboard, and Discord are **out of scope**.

---

## Architecture

```text
┌──────────────────────────────────────────────┐
│ Host macOS                                   │
│                                              │
│ Docker Compose                               │
│ SSH Client → 127.0.0.1:<LAB_SSH_PORT>        │
│     │                                        │
│     ▼                                        │
│  ┌─────────────────────────────────────┐     │
│  │ Container: ai-security-ubuntu-lab   │     │
│  │ OpenSSH Server (port 22 internal)   │     │
│  │ Lab user (LAB_SSH_USER)             │     │
│  │ rsyslog → /var/log/auth-lab/auth.log│     │
│  └──────────────────┬──────────────────┘     │
│                     │ bind mount             │
│                     ▼                        │
│        data/raw/auth/auth.log (host)         │
└──────────────────────────────────────────────┘
```

---

## Docker setup

| Item | Value |
|---|---|
| Base image | `ubuntu:24.04` (official multi-arch; Apple Silicon + amd64) |
| Build context | `ubuntu-server/` |
| Compose service | `ubuntu-test-server` |
| Container name | `ai-security-ubuntu-lab` |
| Network | `ai-security-labnet` (bridge) |
| Host bind | `127.0.0.1:${LAB_SSH_PORT:-2222}:22` |
| Restart policy | `unless-stopped` |
| Healthcheck | `pgrep -x sshd` confirms daemon without SSH handshake noise |

No `platform: linux/amd64` pin — native arm64 on Apple Silicon.

---

## SSH configuration

File: `ubuntu-server/sshd_config`

| Setting | Value | Why |
|---|---|---|
| `PermitRootLogin` | `no` | No root password / root SSH |
| `PermitEmptyPasswords` | `no` | Block empty-password logins |
| `PasswordAuthentication` | `yes` | Controlled lab password tests |
| `UsePAM` | `yes` | Session opened/closed via PAM |
| `LogLevel` | `VERBOSE` | Detailed auth attempt logging |
| `SyslogFacility` | `AUTH` | Route into auth syslog stream |
| `AllowTcpForwarding` | `no` | Reduce lab attack surface |
| `X11Forwarding` | `no` | Not needed for auth-log lab |

sshd runs in foreground: `sshd -D` (entrypoint).

---

## Authentication logging

Ubuntu containers do **not** automatically populate `/var/log/auth.log` without a syslog daemon.

**Chosen mechanism:** `rsyslog` + drop-in `ubuntu-server/rsyslog-auth.conf` writing:

```text
/var/log/auth-lab/auth.log
```

Expected event types (conceptual):

```text
Accepted password ...
Failed password ...
Invalid user ...
session opened ...
session closed ...
```

---

## Test account strategy

| Item | Source |
|---|---|
| Username | `LAB_SSH_USER` env (default placeholder `testuser`) |
| Password | `LAB_SSH_PASSWORD` env (placeholder in `.env.example` only) |
| Creation | Entrypoint `useradd` + `chpasswd` at start |
| Root | Not used as SSH account; root login disabled |

Secrets live in `.env` (gitignored), never in YAML or docs.

---

## Host port strategy

Default: `2222` on loopback only.

```text
127.0.0.1:2222 → container:22
```

Override with `LAB_SSH_PORT` if occupied. Do not bind `0.0.0.0` without an explicit future decision.

---

## Log persistence

**Choice:** Bind-mount persist.

| Behavior | Detail |
|---|---|
| Container restart | Host file `data/raw/auth/auth.log` remains |
| Preserve scenario | Leave the file as-is; optionally copy aside |
| Reset scenario | `./scripts/lab_reset_logs.sh` (backup + truncate) |

Truncate-in-place keeps the bind-mount inode usable by a running rsyslog.

---

## Security boundaries

```text
localhost
Docker private network
project-owned containers
controlled test accounts
```

Forbidden: public scanning, external credential spraying, malware, exploit frameworks, third-party targets.

---

## P2 handoff

| Question | Answer |
|---|---|
| What should P2 monitor? | `data/raw/auth/auth.log` (repo-relative) |
| Format? | Traditional syslog auth lines from OpenSSH/PAM via rsyslog |
| When is a new line produced? | On SSH auth attempts and session open/close against the lab container |
| How to reset/start a new scenario? | `./scripts/lab_reset_logs.sh` then generate events; restart container if logging stalls |

### Exact operator commands

```text
SERVER:     Ubuntu Docker lab (ai-security-ubuntu-lab)
SERVICE:    OpenSSH
HOST:       127.0.0.1
PORT:       LAB_SSH_PORT (default 2222)
LOG SOURCE: data/raw/auth/auth.log

LAB START:  ./scripts/lab_start.sh
            # or: docker compose up -d --build
LAB STOP:   ./scripts/lab_stop.sh
            # or: docker compose stop ubuntu-test-server
LAB HEALTH: ./scripts/lab_status.sh
            # or: docker compose ps
LOG RESET:  ./scripts/lab_reset_logs.sh
```

### Normal event sources for later P2

- successful login
- session opened
- session closed
- controlled isolated login failure (baseline context only — not attack generation)
