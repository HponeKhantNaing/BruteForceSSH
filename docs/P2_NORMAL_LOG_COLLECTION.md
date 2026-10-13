# P2 — Normal Authentication Log Collection

**Phase:** P2  
**Depends on:** P1 (Ubuntu Docker SSH lab)  
**Status:** Implemented and verified (see `P2_VERIFICATION.md`)

---

## Objective

Collect controlled, reproducible **normal / benign** SSH authentication evidence from the real project-owned Ubuntu Docker lab so later phases have a trustworthy baseline of routine behavior.

P2 stores **raw evidence + provenance**. It does **not** build ML feature vectors or final class labels.

---

## Why normal data matters

Without realistic benign sessions, a detector cannot learn what routine authentication looks like. Keyword rules that treat every `Failed password` as malicious will fail. Normal data anchors `NORMAL` behavior, including occasional human mistakes.

---

## Why failed password ≠ attack

P2 includes scenario **N06** — exactly **one** incorrect password, a pause, then a successful login.

That preserves evidence for the P0 rule:

```text
failed password != automatically BRUTE_FORCE
```

Rapid failure bursts belong to **P3**, not P2.

---

## Scenario catalog

| ID | Behavior |
|---|---|
| `N01_SINGLE_SUCCESS` | Connect → accept → open → immediate clean exit → close |
| `N02_COMMAND_SESSION` | Login → benign command (`whoami` / `pwd`) → exit |
| `N03_SHORT_SESSION` | Login → short hold (~3s) → optional `date` → exit |
| `N04_LOW_FREQUENCY_REPEAT` | Two successful sessions with ≥10s gap |
| `N05_SESSION_RECONNECT` | Session → logout → gap → reconnect session |
| `N06_ISOLATED_PASSWORD_MISTAKE` | One failed auth → pause → successful recovery session |

Configuration: `config/p2_normal_scenarios.yaml`

---

## Collection architecture

```text
Normal Scenario Definition
          ↓
Scenario Runner (scripts/p2_collect_normal.py)
          ↓
SSH → 127.0.0.1:LAB_SSH_PORT
          ↓
Ubuntu Test Server (OpenSSH / PAM)
          ↓
rsyslog
          ↓
data/raw/auth/auth.log
          ↓
Byte-offset boundary capture
          ↓
Per-run auth.log + manifest.json
          ↓
index.jsonl + batch summary
```

Automation uses **Paramiko** (password auth only; no agent/keys) so credentials stay in environment variables and `sshpass` is not required.

---

## Scenario boundary strategy

1. Record `start_offset = size(master auth.log)`
2. Execute scenario SSH actions
3. Poll until log size stabilizes (flush wait)
4. Capture `auth.log[start_offset:end_offset]` into the run folder

This isolates runs without resetting the master log every time.

### Modes

| Mode | Behavior |
|---|---|
| Continuous | Master log grows; offsets isolate scenarios |
| Fresh batch | Operator may run `./scripts/lab_reset_logs.sh` before a new batch (never silent) |

---

## Manifest format

Per run: `manifest.json` with provenance fields including:

- `scenario_id`, `run_id`, `collection_batch_id`
- `scenario_intent: normal` (collection intent only — **not** final ML label)
- offsets, SHA-256, actions, event_summary, result

Passwords are **never** stored.

---

## Batch IDs

Each collection invocation uses a `collection_batch_id`, e.g. `P2_BASELINE_20260927T070000Z`.

Summary file: `data/raw/normal/<batch_id>_summary.json`

---

## Raw data integrity

Each captured `auth.log` has `raw_log_sha256` (SHA-256) in the manifest and index.

Do not edit raw captures after checksum generation.

---

## Credential handling

| Item | Source |
|---|---|
| User | `LAB_SSH_USER` |
| Password | `LAB_SSH_PASSWORD` |
| Port | `LAB_SSH_PORT` |

Loaded from `.env` / environment. Never written to manifests, index, summaries, or docs.

---

## Safety boundary

Runner refuses non-local targets. Allowed hosts: `127.0.0.1`, `localhost`.

Only the project container `ai-security-ubuntu-lab` is used.

N06 validates `max_failed_attempts == 1`. Unexpected failure bursts mark the run `failed`.

Reconnect gaps must be ≥ `min_gap_seconds` (default 3; scenarios use 10).

---

## Commands

```bash
# Dry-run (no SSH)
python3 scripts/p2_collect_normal.py --dry-run
# or: ./scripts/p2_collect_normal.sh --dry-run

# Single scenario
python3 scripts/p2_collect_normal.py --scenario N01_SINGLE_SUCCESS --repetitions 1

# Full enabled baseline
python3 scripts/p2_collect_normal.py --all
```

---

## Limitations

- Single lab username and Docker bridge source IP dominate traffic
- Containerized OpenSSH is not identical to every production host
- Baseline size is modest (~30 runs) by design
- Master log may contain unrelated lines outside captured slices (startup, prior sessions)
- `scenario_intent` is not a final event label

---

## P3 handoff

P3 will add **suspicious** and **brute-force** scenarios separately under a different raw tree.

P2 artifacts to reuse:

| Item | Path / command |
|---|---|
| Master auth log | `data/raw/auth/auth.log` |
| Normal raw root | `data/raw/normal/` |
| Index | `data/raw/normal/index.jsonl` |
| Scenario config | `config/p2_normal_scenarios.yaml` |
| Collect all | `python3 scripts/p2_collect_normal.py --all` |
| Collect one | `python3 scripts/p2_collect_normal.py --scenario N01_SINGLE_SUCCESS` |
| Dry-run | `python3 scripts/p2_collect_normal.py --dry-run` |
