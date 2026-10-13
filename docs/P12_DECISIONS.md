# P12 Decisions

| Decision | Choice | Reason |
|---|---|---|
| Consume P11 structured predictions only | JSONL + status | ML already decided |
| Flask localhost dashboard | `127.0.0.1:8080` | Lightweight; no CDN |
| SQLite persistent state | WAL + unique keys | Dedup + restart safety |
| Historical backfill without alerts | first_start_policy | No startup flood |
| Deterministic event/alert keys | SHA-256 canonical JSON | Idempotency |
| final-non-normal Discord | finals only | Prefix mismatch risk |
| ACTIVE_PREFIX dashboard-only | default | Provisional |
| No probability threshold | label-only | Uncalibrated scores |
| 60s source cooldown | same severity | Reduce spam |
| Severity escalation bypass | CRITICAL over WARNING | Important transitions |
| Durable outbox | PENDING before send | Restart consistency |
| Bounded Discord retries | 3 / 1s,2s,4s + Retry-After | Avoid loops |
| Webhook secret from env only | never logged/persisted | Security |
| No raw identities | SRC_RUNTIME_* only | Privacy |
| No model loading/inference | presentation layer | P11 boundary |
