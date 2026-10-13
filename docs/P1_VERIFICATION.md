# P1 — Verification Results

**Date:** 2026-09-27  
**Host:** macOS (Apple Silicon) + Docker Desktop  
**Rule:** Every PASS below was observed at runtime. No invented results.

---

## Summary matrix

```text
Docker config              PASS
Docker build               PASS
Container startup          PASS
Healthcheck                PASS
SSHD validation            PASS
Valid login                PASS
Successful-login log event PASS
Failed login               PASS
Failed-login log event     PASS
Session open/close logs    PASS
Host-visible auth log      PASS
Restart test               PASS
Clean reset workflow       PASS
```

---

## Detailed results

### Docker config

```text
Command: docker compose config
Result: PASS
Notes: service ubuntu-test-server, 127.0.0.1:2222->22, bind mount data/raw/auth
```

### Docker build

```text
Command: docker compose build / docker compose up -d --build
Result: PASS
Image: ai-security-ubuntu-lab:p1
Base: ubuntu:24.04 (arm64 pull on Apple Silicon)
```

### Container startup

```text
Command: docker compose up -d
Result: PASS
Container: ai-security-ubuntu-lab
Status: running
```

### Healthcheck

```text
Command: docker inspect --format='{{.State.Health.Status}}' ai-security-ubuntu-lab
Result: PASS
Observed: healthy
Method: pgrep -x sshd
```

### SSH config validation

```text
Command: docker exec ai-security-ubuntu-lab /usr/sbin/sshd -t
Result: PASS
Also confirmed in entrypoint logs: "sshd configuration validation passed"
```

### Successful login

```text
Target: 127.0.0.1:2222 as LAB_SSH_USER (testuser)
Result: PASS
Evidence: remote command echoed LOGIN_OK
```

### Successful-login log event

```text
Host path: data/raw/auth/auth.log
Result: PASS
Sanitized evidence:
  Accepted password for testuser from 172.18.0.1 port ***** ssh2
  pam_unix(sshd:session): session opened for user testuser ...
  pam_unix(sshd:session): session closed for user testuser
```

### Failed login

```text
Target: same local lab with wrong password
Result: PASS
Client observed: Permission denied
```

### Failed-login log event

```text
Result: PASS
Sanitized evidence:
  Failed password for testuser from 172.18.0.1 port ***** ssh2
```

### Session open/close logs

```text
Result: PASS
Evidence: pam_unix session opened / session closed lines present after successful login
```

### Host-visible auth log

```text
Result: PASS
Path: /Users/.../BruteForceSSH/data/raw/auth/auth.log
Readable with: tail data/raw/auth/auth.log
No container shell required for P2 consumption
```

### Restart test

```text
Command: docker compose restart ubuntu-test-server
Result: PASS
After restart: health=healthy, valid login succeeded, new Accepted password line appended
Test user retained (entrypoint re-applies env password)
```

### Clean reset workflow

```text
Command: ./scripts/lab_reset_logs.sh
Result: PASS
Behavior: backup to auth.log.bak.<UTC>, truncate auth.log in place
Observed empty file after reset (RESET_EMPTY_OK)
```

---

## Policy checks (spot)

| Check | Result |
|---|---|
| `PermitRootLogin no` | PASS (present in sshd_config inside container) |
| `PermitEmptyPasswords no` | PASS |
| `PasswordAuthentication yes` | PASS |
| Host bind `127.0.0.1` only | PASS (`docker compose ps` shows `127.0.0.1:2222->22/tcp`) |
| No Discord / ML / dashboard code added | PASS (scope review) |

---

## Notes

- Early TCP healthcheck (`/dev/tcp`) produced SSH banner noise; replaced with `pgrep -x sshd` before final acceptance.
- `imklog` disabled for containers; compose logs no longer show imklog permission errors after rebuild.
- Local `.env` used for lab credentials; must remain uncommitted.
