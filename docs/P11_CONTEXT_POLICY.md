# P11 Context Policy

## Why continuous stream needs segmentation

Training used one bounded contextual run = one sample. Live logs have no natural RUN END.

## Per-source episode choice

Attackers may rotate usernames from one source. Per-user grouping would destroy `unique_users_*`.

## Why not per-user

`unique_users_total` / `unique_users_60s_max` require multiple users inside one context.

## TRAIN-only timeout derivation

From P8 TRAIN attempt timestamps only:

| Metric | Value (s) |
|--------|-----------|
| Max inter-attempt gap | 15.563426 |
| Median gap | 4.8909685 |
| p95 gap | 8.5934 |
| Chosen idle timeout | 30.0 |
| Safety margin | ≈14.44 |

TEST labels/scores were **not** used.

## Maximum episode duration

300 seconds (matches P7 5-minute horizon). Documented; not silently changed.

## Active prefix

Provisional predictions after each completed logical attempt.

## Final episode

Emitted on IDLE_TIMEOUT / MAX_DURATION / LOG_RESET / PROCESS_STOP. Duration end = last relevant attempt timestamp (not timeout wall clock).

## Restart behavior

V1 state is memory-only. Restart resets active contexts.

## Known mismatch with bounded training runs

Live episode segmentation is a **deployment heuristic**. P9’s 15/15 TEST does **not** validate this policy.
