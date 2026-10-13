# P1 — Decision Log

**Phase:** P1 — Ubuntu Docker Test Server  
**Rule:** Do not silently change P0 decisions. Record P1 technical choices here.

---

## P0 preservation

P0 decisions remain in force:

- Detection scope: authentication / login monitoring
- Classes: `NORMAL` / `SUSPICIOUS` / `BRUTE_FORCE`
- Failed password ≠ automatic brute force
- Offline training / online inference
- Project-owned isolated Docker lab
- UI independent from detection engine
- Primary log source: Ubuntu authentication / SSH logs

No P0 conflicts required a scope change. P1 only materializes the lab server promised in P0.

---

## P1 decisions

| Decision | Choice | Reason | Alternatives | Revisit When |
|---|---|---|---|---|
| Ubuntu base image | `ubuntu:24.04` | Official multi-arch LTS; works on Apple Silicon & amd64 without Rosetta pin | `ubuntu:22.04`; Debian | Image EOL or package issues |
| Apple Silicon compatibility | No `platform:` pin; native arm64 pull | Avoid unnecessary amd64 emulation | Force `linux/amd64` | Dependency requires amd64-only binary |
| SSH port binding | `127.0.0.1:${LAB_SSH_PORT:-2222}:22` | Local-only exposure for lab safety | `0.0.0.0:2222` | Never for default student lab |
| Default host port | `2222` | Avoid colliding with host SSH :22 | Other high ports | Port conflict on host |
| Authentication method | Password auth enabled for lab user | Needed for controlled success/fail tests | Keys-only | If password tests no longer needed |
| Root login policy | `PermitRootLogin no` | Reduce risk; lab uses non-root account | Root with key-only | Never for this lab |
| Empty passwords | Disabled | Hardening | Allow empty (unsafe) | Never |
| Logging mechanism | `rsyslog` → `/var/log/auth-lab/auth.log` | Ubuntu containers lack automatic auth.log without syslog | journald; sshd `-e` stderr only | If rsyslog proves unreliable |
| Auth log location (container) | `/var/log/auth-lab/auth.log` | Dedicated path separate from default OS logs | `/var/log/auth.log` | Path rename for consistency |
| Host mount strategy | Bind mount `./data/raw/auth` | Matches P0 `data/raw/` layout; P2-readable without copy | Named Docker volume | If bind mounts fail on some OS |
| Log persistence policy | Persist across restarts; explicit reset script | Supports scenario collection + clean starts | Ephemeral container FS only | If contamination becomes common |
| Healthcheck strategy | `pgrep -x sshd` (procps) | Confirms daemon without TCP handshake spam in auth.log | `/dev/tcp` probe; `sshd -t` only | If sshd process naming changes |
| Test account strategy | Env `LAB_SSH_USER` / `LAB_SSH_PASSWORD` at entrypoint | No committed secrets; disposable identities | Bake password into image | Never bake secrets |
| Compose networking | Dedicated bridge `ai-security-labnet` | Isolate lab traffic from unrelated compose stacks | Default network only | Multi-service expansion |
| Helper scripts | `lab_start/stop/status/reset_logs` | Reproducible operator workflow | Docs-only commands | If scripts drift from compose |
| Raw log git policy | Ignore `data/raw/auth/**` (keep `.gitkeep`) | Logs contain usernames/IPs/timestamps | Commit sample logs | P6 anonymization / curated samples |

---

## Amendments to P0 artifacts

| Artifact | Change | Why |
|---|---|---|
| `docker-compose.yml` | Replaced empty placeholder with `ubuntu-test-server` | P1 deliverable |
| `config/example.yaml` `lab:` | Expanded with host/port/log path | Non-secret lab contract for P2 |
| `.env.example` | Added `LAB_SSH_PORT` + placeholder lab values | Document required env |
| `.gitignore` | Ignore generated auth logs under `data/raw/auth/` | Privacy / no accidental commit |
| `README.md` | Phase → P1 | Reflect progress |
