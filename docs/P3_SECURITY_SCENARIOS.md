# P3 — Controlled Suspicious / Brute-Force Scenario Collection

**Phase:** P3  
**Depends on:** P1 lab + P2 provenance architecture  
**Status:** Implemented and verified (see `P3_VERIFICATION.md`)

---

## Objective

Produce small, bounded, reproducible authentication-failure scenarios against the
**project-owned localhost Docker lab** so later phases can observe behavioral
differences from the P2 normal baseline.

P3 is **not** a real attack tool. It is a dataset-generation workflow.

---

## Safety boundary

```text
Allowed targets: 127.0.0.1 / localhost only
Hard attempt cap: 30 per run (code)
Hard username cap: 6 per run (code)
Minimum inter-attempt delay: 0.25s (code)
Scenario timeout: 120s (code)
```

Forbidden by design:

- `--host` / `--target` / IP ranges
- password dictionaries / wordlists
- username enumeration / scanning
- parallel attack workers
- proxies / evasion / remote systems

YAML cannot raise code ceilings.

---

## Why P3 exists

P2 captured benign behavior (including N06 = one accidental failure).

P3 adds elevated and concentrated failure patterns so P4–P9 can study:

```text
Normal → Suspicious-like → Brute-force-like
```

without claiming final production thresholds.

---

## Suspicious vs brute-force experimental intent

| Intent | Meaning in P3 |
|---|---|
| `suspicious` | Elevated / unusual failures, still relatively low rate or small clusters |
| `brute_force` | Higher concentration / sustained bursts within hard safety caps |

These are **scenario intents**, not final ML event labels.

---

## Scenario catalog

### Suspicious

| ID | Failures | Users | Timing | Success? |
|---|---:|---:|---|---|
| S01 | 3 | 1 | ~4s gaps | no |
| S02 | 3 | 1 | ~3s gaps | yes (recovery) |
| S03 | 1×3 users | 3 | ~4s gaps | no |
| S04 | 5 | 1 | ~2s gaps | no |

### Brute-force-like

| ID | Failures | Users | Timing | Success? |
|---|---:|---:|---|---|
| B01 | 10 | 1 | ~0.8s gaps | no |
| B02 | 14 | 1 | ~2.5s gaps (sustained) | no |
| B03 | 4×3 users | 3 | ~0.8s gaps | no |
| B04 | 8 | 1 | ~0.8s then success | yes |
| B05 | 5+5 | 1 | burst / 12s pause / burst | no |

Intensity relative to N06 (1 failure) is experimental only — **not** final detection thresholds.

---

## Attempt caps

| Ceiling | Value |
|---|---:|
| `MAX_AUTH_ATTEMPTS_PER_RUN` | 30 |
| `MAX_USERNAMES_PER_RUN` | 6 |
| `MAX_INTENTIONAL_PASSWORDS_PER_RUN` | 3 |
| `MAX_SCENARIO_SECONDS` | 120 |
| `MIN_INTER_ATTEMPT_DELAY` | 0.25 |

---

## Localhost guard

`assert_p3_localhost()` rejects anything except `127.0.0.1` / `localhost`.

---

## Lab user strategy

Primary user: `LAB_SSH_USER`.

Additional disposable accounts created in-container if missing:

```text
labuser1
labuser2
labuser3
```

Same disposable lab password as `LAB_SSH_PASSWORD` (never written to manifests).

Wrong passwords are internal constants (`incorrect_p3_password_*`) and are **not** stored in manifests.

---

## Data flow

```text
Scenario Config
↓
Safety Validator
↓
Localhost SSH Runner (sequential Paramiko)
↓
Ubuntu Docker Lab
↓
OpenSSH Auth Logs
↓
Boundary Capture
↓
Raw Scenario File
↓
Manifest + Index
```

---

## Raw data layout

```text
data/raw/security/
├── README.md
├── index.jsonl
├── suspicious/<SCENARIO>/<run_id>/{auth.log,manifest.json}
└── brute_force/<SCENARIO>/<run_id>/{auth.log,manifest.json}
```

---

## Scenario ground truth

Manifests record planned/actual attempt counts, username counts, gaps, duration, and event summaries.

**SSH attempt count ≠ auth.log line count** — one attempt can emit multiple lines.

---

## Why scenario intent ≠ final ML label

One run produces many log lines. P4 assigns final `NORMAL` / `SUSPICIOUS` / `BRUTE_FORCE` labels carefully. P3 only records experimental intent.

---

## Commands

```bash
python3 scripts/p3_collect_security.py --dry-run
python3 scripts/p3_collect_security.py --scenario S01_FEW_REPEATED_FAILURES --repetitions 1
python3 scripts/p3_collect_security.py --group suspicious
python3 scripts/p3_collect_security.py --group brute-force
python3 scripts/p3_collect_security.py --all
```

---

## Limitations

- Single Docker bridge source IP
- Limited username diversity (4 lab accounts)
- Container timing ≠ production
- Small experimental baseline
- Scenario intent is not event-level ground truth for every line
- Initial P0 numeric thresholds are design aids, not validated detectors

---

## P4 handoff

| Item | Value |
|---|---|
| Normal root | `data/raw/normal/` |
| Normal index | `data/raw/normal/index.jsonl` |
| Security root | `data/raw/security/` |
| Security index | `data/raw/security/index.jsonl` |
| P3 config | `config/p3_security_scenarios.yaml` |
| P2 scenarios | N01–N06 |
| P3 suspicious | S01–S04 |
| P3 brute-force | B01–B05 |
