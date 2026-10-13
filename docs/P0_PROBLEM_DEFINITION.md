# P0 — Problem Definition, ODSC & Detection Scope

**Phase:** P0 — Project Foundation  
**Status:** Planning (no implementation claimed)  
**Scope:** Authentication / login security monitoring only

---

## 1. Real Problem

### 1.1 Current situation

Server authentication logs contain high volumes of routine and non-routine events, including:

- successful login (`Accepted password`)
- failed password attempts (`Failed password`)
- invalid username attempts (`Invalid user`)
- authentication failures
- session opened / session closed
- repeated login attempts from the same or different sources

An administrator may receive hundreds or thousands of such events in a short period. Manually reading every line is impractical during normal operations and especially during an active incident.

### 1.2 Problem

A single log **event** is not the same as a security **problem**.

| Concept | Example | Meaning |
|---|---|---|
| Event / phenomenon | `Failed password for user alice` | Something happened once |
| Security problem | Repeated high-rate failures across usernames from one source within a short window | Suspicious or attack-like *behavior* |

**One failed password does NOT automatically mean attack.**

A legitimate user may mistype a password. Keyword matching on `"Failed password"` therefore creates noise: many false alarms, and little ability to distinguish:

- an ordinary user mistake, from
- probing / credential stuffing style behavior, from
- sustained brute-force activity.

The actual problem this project addresses is:

> Server authentication logs mix large amounts of routine activity with suspicious login behavior. Continuous manual review is impractical, and simple keyword matching cannot reliably separate ordinary mistakes from repeated attack behavior. Administrators need a system that continuously analyzes authentication activity, identifies suspicious behavioral patterns, presents them clearly, and sends timely alerts.

Suspicious behavioral patterns of interest include:

- unusually frequent failed attempts
- many attempts from one source
- many usernames tested by one source
- repeated failures in a short time window
- suspicious failure → success sequences
- other abnormal authentication behavior relative to a defined baseline

### 1.3 Negative impact

Without continuous analysis that goes beyond keywords:

- real attacks may not be noticed quickly
- administrators cannot manually inspect every log line
- keyword-only detection creates false positives (every mistyped password looks like an “attack”)
- important multi-event patterns may be missed when events are viewed in isolation
- notifications may arrive too late to be useful during a demonstration or incident response exercise

### 1.4 Why automation is needed

Automation is useful because authentication threat signals are often **distributed across time and multiple events**. A system can:

- ingest logs continuously from an authorized test environment
- maintain rolling behavioral context (30s / 60s / 5m windows)
- classify activity as `NORMAL`, `SUSPICIOUS`, or `BRUTE_FORCE`
- present structured results to a dashboard
- alert only when configured thresholds / classes warrant notification

This reduces cognitive load and improves consistency compared with ad-hoc log grepping.

---

## 2. ODSC

### 2.1 Objective

Create a real-time security monitoring system capable of analyzing authentication-related server logs and distinguishing routine behavior from suspicious login activity using machine learning and behavioral analysis.

The system is designed for an **isolated, authorized local test environment** (project-owned Docker Ubuntu test server). It must not depend on attacking third-party systems.

### 2.2 Deliverables (eventually across P1–P12)

| Deliverable | Notes |
|---|---|
| Isolated Ubuntu Docker test server | Project-owned lab target only |
| Authentication log source | SSH/auth-style events from the test server |
| Log collection pipeline | Continuous or near-real-time ingestion |
| Labeled dataset | Canonical schema with `NORMAL` / `SUSPICIOUS` / `BRUTE_FORCE` |
| Preprocessing pipeline | Cleaning, normalization, structured fields |
| Feature extraction pipeline | Text (TF-IDF) + behavioral numeric features |
| Trained ML model | Offline training; not retrained on every monitor start |
| Evaluation report | Precision, Recall, F1, Confusion Matrix, per-class metrics |
| Saved model artifacts | Versioned export under `models/` |
| Real-time monitoring service | Online inference path |
| Threat/event scoring | Class + confidence for each scored event |
| Dashboard | Consumes structured API events; Mobbin UI later |
| Discord notification integration | Alert channel only; webhook via env var |
| Test scenarios | Reproducible normal / suspicious / brute-force runs |
| Technical documentation | Phase docs + README + decisions log |

**P0 itself delivers only:** problem definition, scope, architecture, data/ML strategy, configuration defaults, and project skeleton — not a running detector.

### 2.3 Success Criteria

Success is **not** defined only as “high accuracy.”

#### Functional / operational criteria

- Normal activities can be monitored and classified without treating every failure as an attack
- Failed password events are **not** automatically labeled or predicted as `BRUTE_FORCE`
- Repeated suspicious behavior can be identified using behavioral context, not keywords alone
- Real-time processing works without noticeable delay for a student demo
- Prediction latency is acceptable for local demonstration use
- Discord alerts trigger only when the configured class/threshold is met
- Dashboard receives structured detection events over a stable API contract
- Detection engine works independently from UI (UI must not contain detection logic)
- Test environment can be reproduced via Docker Compose / documented scripts

#### ML / evaluation criteria

- False positives and false negatives are measured and reported
- Model performance is evaluated using Precision, Recall, F1, and Confusion Matrix (plus per-class metrics)
- Training / test leakage is avoided via scenario-aware splits
- Offline training is separated from online inference

#### Initial project targets — subject to revision after baseline experiments

> These are **planning targets only**. They are **not** achieved results. Values will be revised after P8–P9 baseline experiments.

| Area | Initial target (planning) |
|---|---|
| Per-class F1 (`NORMAL`, `SUSPICIOUS`, `BRUTE_FORCE`) | ≥ 0.70 on independent test scenarios |
| False positive rate for `BRUTE_FORCE` on pure normal scenarios | Low enough for demo clarity (exact rate after baseline) |
| End-to-end event scoring latency (parse → features → infer) | Typically &lt; 250 ms on a laptop for a single event under light load |
| Alert policy | Discord fires only for configured classes (default: `BRUTE_FORCE`; optionally `SUSPICIOUS`) |
| Leakage control | No random line-level split across the same `scenario_id` |

Do **not** fabricate achieved scores in later docs until real experiments exist.

---

## 3. Detection Scope (Version 1)

### 3.1 In scope

Authentication / login security monitoring on the project’s isolated Ubuntu Docker test server, including:

- successful and failed authentication events
- invalid user attempts
- session open/close related to authentication context
- behavioral aggregation over rolling time windows
- three-class classification: `NORMAL`, `SUSPICIOUS`, `BRUTE_FORCE`

### 3.2 Out of scope (Version 1)

The system will **NOT** initially detect or claim to detect:

- network IDS/IPS style packet attacks
- malware / ransomware
- web application exploits (SQLi, XSS, etc.)
- privilege escalation beyond auth log evidence
- lateral movement across real networks
- DDoS / volumetric network attacks
- full SIEM correlation across heterogeneous enterprise log sources
- attacks against any third-party or unauthorized system

Keyword-only “alert on Failed password” is explicitly **not** the product goal.

---

## 4. Detection Classes (Version 1)

```text
NORMAL
SUSPICIOUS
BRUTE_FORCE
```

### 4.1 NORMAL

Routine authentication behavior consistent with legitimate use or isolated mistakes.

**Examples:**

- successful login
- normal session open
- session close
- isolated failed password attempt
- low-frequency ordinary authentication failures

**Rule of thumb:** One failed login should generally **not** become `BRUTE_FORCE`.

### 4.2 SUSPICIOUS

Activity above expected normal rates or patterns, but with **insufficient** evidence to confidently call confirmed brute-force behavior.

**Examples:**

- repeated failures above normal but below brute-force baseline thresholds
- unusual rate of login failures for a short period
- attempts against several usernames without extreme burst intensity
- abnormal login sequence (e.g., clustered failures then unexpected success) that warrants attention

`SUSPICIOUS` is an intermediate class for operator attention — not an automatic confirmation of attack.

### 4.3 BRUTE_FORCE

Must be defined using **behavioral evidence**, not a single keyword match.

Evidence may include combinations of:

- failed attempts within 30 seconds
- failed attempts within 60 seconds
- failed attempts within 5 minutes
- number of unique usernames attempted
- source identity used for grouping (IP / source_id)
- attempt rate
- time gaps between attempts

**Baseline configurable thresholds (planning defaults — to be validated experimentally):**

| Signal | Baseline default | Notes |
|---|---|---|
| `failed_count_30s` | ≥ 8 | Strong short-burst signal |
| `failed_count_60s` | ≥ 12 | Medium window intensity |
| `failed_count_5m` | ≥ 30 | Sustained pressure |
| `unique_users_60s` | ≥ 5 | Credential / username spraying style signal |
| `attempt_rate` (attempts/sec over medium window) | ≥ 0.25 | Rate context |

Labeling and alerting must use **policy + evidence**, not a single hard rule in isolation. Exact numeric cutoffs are configuration defaults in `config/example.yaml` and must be revisited after controlled experiments (P3–P9).

**Forbidden simplistic rule:**

```text
"Failed password" = BRUTE_FORCE   ❌
```

---

## 5. Laboratory / Security Rule

All testing, failed-login generation, simulated brute-force behavior, dataset collection, and security experiments must occur **only** against systems owned and controlled by this project (the future Docker Ubuntu test server).

Do not design workflows that target third-party hosts, public SSH endpoints, or unauthorized infrastructure.

---

## 6. Limitations (problem / scope level)

- This is not a full SIEM
- This is not an IDS replacement
- Version 1 focuses on authentication logs only
- One failed login does not prove an attack
- ML predictions will be probabilistic
- Docker lab fidelity ≠ production infrastructure
- Discord is only an alerting channel, not a detection authority

Full limitation list is also mirrored in `P0_SYSTEM_ARCHITECTURE.md` and `P0_DECISIONS.md`.
