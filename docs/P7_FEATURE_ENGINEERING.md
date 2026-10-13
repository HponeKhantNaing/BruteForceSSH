# P7 Feature Engineering

## Objective

Convert P6 canonical data into:

1. Text samples for an **unfitted** TF-IDF pipeline
2. Deterministic behavioral numeric features from logical attempts
3. Separate targets / split-group metadata

No classifier training in P7.

## Inputs

| File | Role |
|------|------|
| `data/processed/p6/canonical_runs.jsonl` | sample_id, targets metadata, duration |
| `data/processed/p6/canonical_sequences.jsonl` | `canonical_text` |
| `data/processed/p6/canonical_attempts.jsonl` | logical SUCCESS/FAILURE attempts |
| `data/processed/p6/dataset_manifest.json` | P6 version + external policy |

## Sample Unit

```text
1 contextual run = 1 ML sample
```

Verified: **75** samples (NORMAL 30 / SUSPICIOUS 20 / BRUTE_FORCE 25).

## Text Feature Source

`canonical_text` from P6 sequences. P7 does not reparse raw logs.

## Why TF-IDF Is Not Fitted in P7

Fitting on all 75 samples would leak test vocabulary/IDF into training.  
P8 fits TF-IDF on **TRAIN only**, then transforms val/test.

## Behavioral Feature Definitions

See `data/features/p7/feature_schema.json` and `config/p7_features.yaml`.

Core set (~22 defaults): totals, ratios, duration, rate, rolling failure/success maxima (30s/60s/5m), user diversity, inter-attempt gaps, failure streak, success-after-failure, failures-before-first-success, first/last outcomes.

## Event vs Attempt Distinction

`failed_attempts` counts **logical** FAILURE attempts from `canonical_attempts.jsonl`.  
Never `AUTH_FAILURE + PAM_AUTH_FAILURE` event-role sums.

## Rolling Window Semantics

Inclusive closed interval `[t - W, t]` evaluated at each attempt timestamp as anchor.  
No future attempts (`timestamp > t`).

## Timing Features

Inter-attempt gaps: min/mean/median/std (0 when single attempt) + `has_multiple_attempts`.

## User Diversity

Uses pseudonymous `USR_*` IDs. Source identity is diagnostic only (lab has SRC_001).

## Failure/Success Sequence Features

`max_failure_streak`, `success_after_failure`, `failures_before_first_success`.

## Constant Features

Diagnosed in `constant_features.json`. Constants disabled by default (none in current build). Near-constants flagged.

## Small Dataset Considerations

~75 samples → keep ~20 numeric features. Warn if samples/feature ratio is low.

## Leakage Prevention

Targets, scenario IDs, collection phase, raw paths, raw IPs/usernames excluded from features/text.

## Train-Serving Parity

`compute_behavior_features(attempt_history)` reusable online with historical attempts only.

## Known Lab-Scenario Bias

Feature distributions may reflect controlled scenario design. Flagged for P9; not production traffic.

## P8 Handoff

```text
data/features/p7/behavioral_features.jsonl
data/features/p7/text_samples.jsonl
data/features/p7/targets.jsonl
data/features/p7/feature_schema.json
data/features/p7/feature_manifest.json
```

P8: leakage-safe split → fit TF-IDF/scaler on TRAIN → hybrid train.
