# rf-behavior-lab-v1.1.0

Packaged Random Forest SSH auth behavior classifier for the lab prototype.

## What this is

- **Model ID:** `random_forest_behavior`
- **Version:** `1.1.0`
- **Channel:** `lab`
- **Maturity:** `CONTROLLED_LAB_VALIDATED`
- **Representation:** `behavior_raw` (22 raw behavioral features; no TF-IDF; no StandardScaler)

This is **not** production-proven. P9 TEST was 15 held-out controlled runs / 3 scenario groups.

## Classes

`NORMAL` · `SUSPICIOUS` · `BRUTE_FORCE`

Internal `model.classes_` order is recorded in `MANIFEST.json` / `schema/feature_contract.json`.

## Required input

Provide all 22 features by name (order enforced by contract). Unknown fields are rejected.

```
total_attempts
failed_attempts
successful_attempts
failure_ratio
duration_seconds
attempt_rate_per_second
failed_count_30s_max
failed_count_60s_max
failed_count_5m_max
success_count_5m_max
unique_users_total
unique_users_60s_max
has_multiple_attempts
min_inter_attempt_gap_seconds
mean_inter_attempt_gap_seconds
median_inter_attempt_gap_seconds
std_inter_attempt_gap_seconds
max_failure_streak
success_after_failure
failures_before_first_success
first_attempt_failed
last_attempt_success
```

## Validate / smoke

From repository root:

```bash
python3 scripts/p10_export_model.py --validate-release
python3 scripts/p10_export_model.py --smoke-test
```

Offline only — no live logs, no Discord, no network.

## Probabilities

`predict_proba` values are **uncalibrated**. Do not treat them as calibrated confidence or true risk.

## Limitations

- Small dataset; controlled lab scenarios; single-source environment
- Limited user diversity; only 3 held-out TEST scenario groups
- Uncalibrated probabilities
- Trained on **bounded contextual runs** (`one run = one sample`). Continuous real-time inference requires a defined runtime context/session policy (P11) without changing feature semantics.

## P11 handoff

Use this release root, `schema/feature_contract.json`, and `MANIFEST.json`. Reproduce P7 logical-attempt + inclusive `[t-W, t]` window semantics exactly.
