# P0 — System Architecture & Component Responsibilities

**Phase:** P0 — Project Foundation  
**Status:** Architecture planning — components are not implemented yet

---

## 1. Design principles

1. **Problem-first:** detect suspicious authentication *behavior*, not keywords alone
2. **Lab-only target:** project-owned Docker Ubuntu test server
3. **Separation of concerns:** collector ≠ parser ≠ features ≠ model ≠ alerts ≠ UI
4. **Offline training / online inference** separation
5. **UI independence:** Mobbin-inspired dashboard can be swapped without changing the detection engine
6. **Config over hardcoding**
7. **No secrets in source control**

---

## 2. High-level architecture

```text
┌─────────────────────────────┐
│ Ubuntu Docker Test Server   │
│                             │
│ SSH/Auth Events             │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Log Collector               │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Event Parser                │
│                             │
│ Parse:                      │
│ timestamp                   │
│ source                      │
│ username                    │
│ event type                  │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Rolling Window Engine       │
│                             │
│ 30 sec                      │
│ 60 sec                      │
│ 5 min                       │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Feature Builder             │
│                             │
│ Text + Behavioral Features  │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ ML Inference Engine         │
│                             │
│ NORMAL                      │
│ SUSPICIOUS                  │
│ BRUTE_FORCE                 │
└──────────────┬──────────────┘
               │
        ┌──────┴─────────┐
        ▼                ▼
 Event Store       Alert Manager
        │                │
        ▼                ▼
 Dashboard         Discord Webhook
```

---

## 3. Planned project structure

```text
ai-security-log-monitor/
│
├── README.md
├── .gitignore
├── .env.example
├── requirements.txt
├── docker-compose.yml          # planned (P1+); may be empty/stub until then
│
├── config/
│   └── example.yaml
│
├── docs/
│   ├── P0_PROBLEM_DEFINITION.md
│   ├── P0_ML_DEFINITION.md
│   ├── P0_DATA_STRATEGY.md
│   ├── P0_DATA_SCHEMA.md
│   ├── P0_LABELING_POLICY.md
│   ├── P0_SYSTEM_ARCHITECTURE.md
│   ├── P0_DECISIONS.md
│   ├── P0_ACCEPTANCE_CHECKLIST.md
│   └── PROJECT_ROADMAP.md
│
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
│
├── models/                     # trained artifacts later (P10)
│
├── src/
│   ├── collection/
│   ├── parsing/
│   ├── features/
│   ├── training/
│   ├── inference/
│   ├── detection/
│   ├── alerts/
│   ├── api/
│   └── common/
│
├── dashboard/                  # Mobbin-inspired UI later (P12)
├── ubuntu-server/              # Docker server definition (P1)
├── scripts/
└── tests/
```

Do not place the entire pipeline in one Python file.

---

## 4. Component responsibilities

### 4.1 collector (`src/collection/`)

| | |
|---|---|
| **Responsibility** | Read / follow authentication logs from the lab server or mounted log source |
| **Input** | Log file path, Docker log stream, or equivalent configured source |
| **Output** | Raw log lines with ingest metadata |
| **Dependencies** | Config; lab server availability |
| **Must NOT** | Parse semantics deeply, classify threats, send Discord alerts, train models |

### 4.2 parser (`src/parsing/`)

| | |
|---|---|
| **Responsibility** | Convert raw lines into structured events |
| **Input** | Raw log lines |
| **Output** | `timestamp`, `source_ip`/`source_id`, `username`, `event_type`, `raw_log` |
| **Dependencies** | Log format assumptions for the lab image |
| **Must NOT** | Compute rolling windows, run ML, alert, render UI |

### 4.3 window engine (`src/features/` or dedicated module under features/detection)

| | |
|---|---|
| **Responsibility** | Maintain rolling 30s / 60s / 5m state per `source_id` |
| **Input** | Structured events |
| **Output** | Window aggregates for the current event |
| **Dependencies** | Parser output; window config |
| **Must NOT** | Own ML model weights, Discord side effects, dashboard styling |

### 4.4 feature builder (`src/features/`)

| | |
|---|---|
| **Responsibility** | Build hybrid feature vectors (clean text + behavioral numerics) |
| **Input** | Structured event + window aggregates |
| **Output** | Feature record aligned with schema |
| **Dependencies** | Window engine; text cleaning rules |
| **Must NOT** | Fit final classifier during monitoring; decide Discord delivery |

### 4.5 ML model artifacts (`models/` + training in `src/training/`)

| | |
|---|---|
| **Responsibility** | Offline fit of baseline classifier and vectorizer; export versioned artifacts |
| **Input** | Processed labeled dataset |
| **Output** | Saved model + vectorizer + metadata |
| **Dependencies** | scikit-learn style stack; config |
| **Must NOT** | Run automatically on every monitor start; call Discord; scrape unauthorized hosts |

### 4.6 inference engine (`src/inference/`)

| | |
|---|---|
| **Responsibility** | Load artifacts; predict class + confidence |
| **Input** | Feature vector / feature record |
| **Output** | `prediction`, `confidence`, probabilities |
| **Dependencies** | Exported model artifacts |
| **Must NOT** | Relabel gold datasets; contain UI layout; hardcode webhook URLs |

### 4.7 detection orchestration (`src/detection/`)

| | |
|---|---|
| **Responsibility** | Wire parse → windows → features → inference into a monitoring loop |
| **Input** | Config + live events |
| **Output** | Detection events for store/API/alerts |
| **Dependencies** | Collector, parser, features, inference |
| **Must NOT** | Embed Mobbin visual design; own Discord message formatting policy beyond calling alert manager |

### 4.8 event store

| | |
|---|---|
| **Responsibility** | Persist recent detection events for dashboard queries |
| **Input** | Detection events |
| **Output** | Queryable event history |
| **Dependencies** | Local storage choice (deferred; keep simple in V1) |
| **Must NOT** | Perform classification; send alerts directly |

### 4.9 alert manager (`src/alerts/`)

| | |
|---|---|
| **Responsibility** | Apply alert policy; notify Discord when thresholds/classes match |
| **Input** | Detection events + alert config + `DISCORD_WEBHOOK_URL` env |
| **Output** | Alert send attempts / status records |
| **Dependencies** | Environment secrets; network |
| **Must NOT** | Decide ground-truth attack labels; re-run ML; attack external systems |

**Critical:** Discord integration must **NOT** determine whether something is an attack. It only notifies based on already-computed detection results and policy.

### 4.10 dashboard API (`src/api/`)

| | |
|---|---|
| **Responsibility** | Expose structured detection events and system status to the frontend |
| **Input** | Event store / detection stream |
| **Output** | JSON API responses |
| **Dependencies** | Event store; auth optional later |
| **Must NOT** | Contain detection logic; train models |

### 4.11 dashboard frontend (`dashboard/`)

| | |
|---|---|
| **Responsibility** | Present live status using a future Mobbin reference design |
| **Input** | Dashboard API JSON |
| **Output** | UI for operators |
| **Dependencies** | API contract |
| **Must NOT** | Contain detection logic; compute BRUTE_FORCE labels locally as authority |

### 4.12 configuration (`config/`)

| | |
|---|---|
| **Responsibility** | Central non-secret defaults (windows, classes, poll interval, feature flags) |
| **Input** | YAML files + env overrides for secrets |
| **Output** | Typed settings for all components |
| **Must NOT** | Store webhook URLs or passwords in committed files |

### 4.13 logging (`src/common/`)

| | |
|---|---|
| **Responsibility** | Application logs for pipeline health/debug |
| **Must NOT** | Replace security event store; print secrets |

### 4.14 testing (`tests/`)

| | |
|---|---|
| **Responsibility** | Unit/integration tests for parser, windows, policies, API contracts |
| **Must NOT** | Require attacking non-lab systems |

---

## 5. Mobbin UI readiness (no visual design in P0)

Final dashboard visuals will follow a **Mobbin reference provided later by the user**.

P0 prepares only the **data interface**.

### 5.1 Detection event contract (minimum)

```json
{
  "timestamp": "...",
  "source": "...",
  "event_type": "...",
  "prediction": "SUSPICIOUS",
  "confidence": 0.82,
  "failed_count_60s": 5,
  "unique_users_60s": 3,
  "raw_log": "..."
}
```

Additional optional fields may include other behavioral features, `scenario_id` (if known), and alert status.

### 5.2 Possible future dashboard sections (content only — not layout)

- Live Logs
- Threat Feed
- Current Threat Status
- Normal vs Suspicious vs Brute Force counts
- Attack timeline
- Source activity
- ML confidence
- Recent Discord alerts
- System status

**Do not invent final styling in P0.**

### 5.3 Backend / frontend separation

```text
Detection Engine  →  Event Store / API  →  Dashboard Frontend
                         ↓
                   Alert Manager → Discord
```

The Mobbin UI may be replaced or redesigned without changing collector/parser/window/feature/model code, as long as the JSON contract remains stable or versioned.

---

## 6. Secrets strategy

| Secret | Storage |
|---|---|
| `DISCORD_WEBHOOK_URL` | Environment variable / `.env` (gitignored) |
| Lab SSH passwords | Local env / Compose secrets; disposable test creds only |
| Future API keys | Env only |

Provide `.env.example` with empty placeholders. Never commit real secrets.

---

## 7. Runtime vs training topology

```text
[Training workstation / scripts]
   labeled data → train → models/*.joblib (or equivalent)

[Monitoring runtime]
   lab logs → collect → parse → windows → features → load model → infer
        → event store → API → dashboard
        → alert manager → Discord (optional)
```

---

## 8. Platform assumptions

- Local development may use macOS (including Apple Silicon)
- Lab target runs via Docker; avoid unnecessary arch-specific assumptions
- No cloud infrastructure required at P0 (or for the core V1 demo path)
- No GPU required
- No paid services required for core functionality

---

## 9. Limitations

- Not a full SIEM
- Not an IDS replacement
- Version 1 focuses on authentication logs
- Model quality depends on dataset quality
- Simulated data alone is insufficient for generalization
- Unseen attack patterns may be missed
- ML predictions are probabilistic
- One failed login does not prove an attack
- Docker test environment does not perfectly reproduce production infrastructure
- IP addresses and usernames must be handled carefully (grouping vs memorization)
- Discord is only an alerting channel
- Public datasets may introduce domain mismatch if used carelessly
