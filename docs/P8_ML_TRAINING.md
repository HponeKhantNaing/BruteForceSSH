# P8 ML Training

## Objective

Build leakage-safe experimental model artifacts from P7 features using scenario-group splits and TRAIN-only preprocessing. No winner. No TEST metrics.

## P7 Inputs

- `data/features/p7/behavioral_features.jsonl`
- `data/features/p7/text_samples.jsonl`
- `data/features/p7/targets.jsonl`
- `data/features/p7/feature_schema.json`
- `data/features/p7/feature_manifest.json`

## Why Split Happens Before Fitting

Fitting TF-IDF/scaler on all samples before splitting leaks validation/test statistics into training.

## Scenario-Grouped Split

Group key: `scenario_id`. Same scenario never crosses TRAIN/VALIDATION/TEST.  
Verified structure: NORMAL 6 / SUSPICIOUS 4 / BRUTE_FORCE 5 scenario groups.

## Train / Validation / Test Policy

Approximate 60/20/20 by scenario groups within each class. Group integrity > exact percentages.

## Test Set Lock

TEST is unused for fit, tuning, selection, and metrics. P9 owns evaluation.

## TF-IDF Train-Only Fit

Uses P7 config; `fit(train_text)` only; transform for val/test.

## Numeric Scaling Train-Only Fit

`StandardScaler.fit(train_behavior)` only.

## Hybrid Representation

`scipy.sparse.hstack(TF-IDF, scaled_behavior)`.

## Models

| Model | Representation |
|-------|----------------|
| Logistic Regression Hybrid | text + behavior (primary baseline) |
| Logistic Regression Text | text |
| Logistic Regression Behavior | behavior (scaled) |
| Linear SVM Hybrid | text + behavior |
| Multinomial NB | text only (non-negative) |
| Random Forest | behavior (unscaled) |

## Why Models Use Different Representations

NB needs non-negative inputs; trees do not need scaling; linear models benefit from hybrid sparse+dense.

## Artifact Layout

- `artifacts/p8/preprocessing/`
- `artifacts/p8/models/`
- `data/modeling/p8/`

## Reproducibility

`random_seed=42`, locked `split_manifest.json`, hashed inputs/artifacts.

## Limitations

Small n (~45 train), controlled lab bias, single source, limited users, small TF-IDF vocab, uncalibrated probabilities.

## Why No Winner Is Chosen in P8

Comparison requires locked validation/test evaluation → P9.

## P9 Handoff

Frozen split + preprocessors + models. P9 must not refit preprocessing before baseline evaluation.
