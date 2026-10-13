# V1 System Architecture

```text
Ubuntu/OpenSSH (P1 Docker lab)
        ↓
auth.log  (data/raw/auth/auth.log)
        ↓
P11 Parser + Logical Attempt Reconstruction
        ↓
Per-Source Episode Context
        ↓
22 Behavioral Features (P7 semantics)
        ↓
P10 Random Forest Release (rf-behavior-lab-v1.0.0)
        ↓
P11 Prediction JSONL
        ↓
P12 Ingestion + SQLite
       ↙            ↘
Dashboard          Alert Policy (p12-alert-v1)
                        ↓
                   Discord Outbox
                        ↓
                     Discord (optional)
```

## Boundaries

| Layer | Owns |
|-------|------|
| P9 | Formal model evaluation |
| P10 | Frozen model bundle |
| P11 | Inference + feature parity |
| P12 | Dashboard + alert delivery |

P12 does **not** parse raw SSH logs or load/call the ML model.

## Maturity

```text
CONTROLLED-LAB V1
```

Not a production security guarantee.
