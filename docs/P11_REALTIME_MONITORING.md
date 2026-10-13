# P11 — Real-Time ML Monitoring Integration

## Objective

Convert continuous lab auth logs into P7-compatible behavioral contexts, validate against the P10 feature contract, and emit structured predictions from the frozen RF model. No dashboard, Discord, or prevention.

## P10 Release Input

`artifacts/p10/releases/rf-behavior-lab-v1.0.0/` — verified via checksums before load.

## Selected Model

`random_forest_behavior` · `behavior_raw` · 22 features · SHA `6176bded…4ce69`

## Why No TF-IDF / Scaling

Selected representation is raw behavioral features only.

## Live Log Source

`data/raw/auth/auth.log` (Docker bind from `/var/log/auth-lab`). Default `start_at=end`.

## Streaming Parsing

P6 `parse_auth_line` + P4 `event_roles` patterns.

## Logical Attempt Reconstruction

Reuses P6 `reconstruct_attempts` for historical parity. Streaming path pairs PAM+AUTH_FAILURE → one FAILURE; SESSION lines do not create attempts.

## Per-Source Activity Episodes

Group by source (not username) so `unique_users_*` remains meaningful. Runtime tokens: `SRC_RUNTIME_*` / `USR_RUNTIME_*`.

## Context Policy

TRAIN-only audit: max inter-attempt gap ≈ 15.56s → idle timeout **30s** (safety margin). Max episode duration **300s**. Not tuned on TEST.

## Active Prefix vs Episode Final

- `ACTIVE_PREFIX` after each completed logical attempt — **provisional**
- `EPISODE_FINAL` on idle/max-duration/stop — final within episode; duration uses last attempt time (idle wait not added)

## Exact 22 Features

From P10 `feature_contract.json`, computed via P7 `compute_behavior_features`.

## Rolling Window Semantics

Inclusive `[t-W, t]` for 30 / 60 / 300 seconds.

## Train-Serving Parity

Historical feature parity **75/75**. Attempt parity **345 FAILURE / 50 SUCCESS**.

## Runtime Prediction Output

`data/runtime/p11/predictions.jsonl` — uncalibrated probabilities; `release_id` stamped.

## Privacy

No raw IP / username / password in persisted outputs.

## Log Rotation / Restart

Truncation/replacement closes contexts with `LOG_RESET`. Process restart = memory-only state loss (`PROCESS_STOP` / `PROCESS_RESTART`).

## Latency

Lab p95 processing/inference target ≤ 1000 ms (measured locally).

## Limitations

Controlled-lab model; small data; active-prefix distribution mismatch; episode segmentation is a deployment heuristic not validated by P9 TEST.

## P12 Handoff

Consume structured predictions / runtime events / status. Define alert policy separately.
