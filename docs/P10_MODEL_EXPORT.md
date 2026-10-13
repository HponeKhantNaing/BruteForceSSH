# P10 — Model Export / Versioning

## Objective

Package the exact P9-selected, P8-trained model into a versioned, hash-verifiable, inference-ready release bundle. P10 is **release engineering**, not model development.

## Frozen P9 Selection

| Field | Value |
|-------|-------|
| Selected model | `random_forest_behavior` |
| Representation | `behavior_raw` |
| Source artifact | `artifacts/p8/models/random_forest_behavior.joblib` |
| Selection lock | required before TEST |
| TEST models evaluated | 1 |
| P9 fit calls | 0 |

## Why No Retraining Occurs

P9 already selected and evaluated the model. Retraining / refitting / reselection would break provenance and evaluation credibility. P10 only **copies** the frozen artifact.

## Selected Model

`random_forest_behavior` — `sklearn.ensemble.RandomForestClassifier` inside a joblib dict payload.

## Representation

Raw behavioral features only (`behavior_raw`).

- TF-IDF: **not required**
- StandardScaler: **not required**

## Versioning Strategy

| Field | Value |
|-------|-------|
| Release ID | `rf-behavior-lab-v1.0.0` |
| Model version | `1.0.0` |
| Channel | `lab` |
| Maturity | `CONTROLLED_LAB_VALIDATED` |

SemVer: PATCH = packaging/docs; MINOR = compatible contract extension; MAJOR = retrain / feature / label break. Releases are **immutable**.

## Feature Contract

Authoritative order from `artifacts/p8/preprocessing/behavior_feature_order.json` (22 features). Named inputs only; unknown fields rejected; non-finite / invalid ranges / impossible relations rejected.

Window policy (P7): inclusive closed `[t-W, t]` for 30s / 60s / 300s.

## Input Validation

See `schema/input.schema.json` and `src/export/schema_validator.py`.

## Output Contract

`predicted_label` ∈ {NORMAL, SUSPICIOUS, BRUTE_FORCE} plus **uncalibrated** `class_probabilities`. No custom thresholds.

## Uncalibrated Probabilities

`predict_proba` is exposed but must not be called confidence / certainty / calibrated risk.

## Release Manifest

`MANIFEST.json` records release ID, SHA-256, representation, feature-order hash, class labels, `model.classes_` order, lock/receipt hashes.

## Provenance

`metadata/provenance.json` chains P2/P3 → P4 → P6 → P7 → P8 → P9 → P10 with hashes.

## Checksums

`CHECKSUMS.sha256` covers important files. The checksum file itself is excluded from its own list.

## Environment Compatibility

Recorded in `metadata/environment.json` / `compatibility.json`. Only tested versions are claimed.

## Bundle Validation

`python3 scripts/p10_export_model.py --validate-release`

## Offline Smoke Test

`python3 scripts/p10_export_model.py --smoke-test`

Packaging regression only — **not** accuracy evaluation. No live logs / Discord / network.

## Limitations

Small controlled lab set; 3 TEST scenario groups; uncalibrated probabilities; run-level training context vs continuous-stream serving gap.

## P11 Handoff

Consume `artifacts/p10/releases/rf-behavior-lab-v1.0.0/`. Reproduce P7 logical-attempt + window semantics. Define stream→context policy **without** changing feature meaning.
