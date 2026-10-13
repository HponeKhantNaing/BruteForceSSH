# P12 — Dashboard + Discord Alert Integration

## Objective

Present P11 structured predictions on a localhost dashboard and deliver Discord alerts via a durable outbox — without reparsing SSH logs or running ML inference.

## P11 Structured Inputs

- `data/runtime/p11/predictions.jsonl`
- `data/runtime/p11/runtime_events.jsonl`
- `data/runtime/p11/status.json`

## Why P12 Does Not Parse Raw Logs

Threat classification already happened in P11. P12 is presentation + notification policy.

## Dashboard Architecture

Flask app on `127.0.0.1:8080`, polling `/api/*` every ~1s. Local CSS/JS only.

## Alert Policy

See `docs/P12_ALERT_POLICY.md`. Default Discord mode: **final_non_normal**.

## ACTIVE_PREFIX / EPISODE_FINAL

Provisional prefixes are dashboard-only. Finals for SUSPICIOUS/BRUTE_FORCE enqueue Discord.

## Why Probabilities Are Not Alert Thresholds

Scores are uncalibrated. Policy uses `predicted_label` only.

## Deduplication / Cooldown / Escalation

SHA-256 `event_key` + `alert_key`. 60s same-source cooldown; higher severity bypasses.

## Historical Backfill

First start ingests existing P11 history with `alert_eligible=false` (0 Discord).

## SQLite / Outbox

`data/runtime/p12/p12_state.sqlite3` — WAL, transactional checkpoint, PENDING→SENT outbox.

## Discord

Env-only webhook. Bounded retries. Failures do not stop dashboard/ingestion.

## Privacy / Localhost

No raw IP/username/password. Default bind `127.0.0.1`. For local controlled-lab use only.

## V1 Limitations

Controlled-lab model; provisional prefixes; Discord is application policy; webhook delivery is best-effort externally.
