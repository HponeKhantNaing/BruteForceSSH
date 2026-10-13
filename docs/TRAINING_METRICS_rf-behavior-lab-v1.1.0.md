# Training metrics — `rf-behavior-lab-v1.1.0`

**Generated:** 2026-10-08T13:21:39.339825+00:00

## Dataset

- Source: controlled-lab P4/P7 features (P5 public datasets **not** merged — Case B)
- Samples after lab synthetic augmentation: **3000** (from 75 originals × 40)
- Train / Validation / Test: **1800** / **600** / **600**
- Scenario groups (0 overlap): train 9 · val 3 · test 3
- Baseline frozen at: `data/features/p7_baseline_75/`

## Selected model

- **random_forest_behavior** (`behavior_raw`)
- Selection: highest validation macro_f1 (primary=`macro_f1` = **0.9967** on validation)
- RF config: n_estimators=500, max_depth=12

## Held-out TEST metrics (selected model only)

| Metric | Value |
|---|---|
| Accuracy | **1.0000** |
| Balanced accuracy | 1.0000 |
| Macro precision | 1.0000 |
| Macro recall | **1.0000** |
| Macro F1 | **1.0000** |
| Weighted F1 | 1.0000 |
| Min class recall | 1.0000 |
| Correct / Total | 600/600 |

### Per-class (TEST)

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| NORMAL | 1.0000 | 1.0000 | 1.0000 | 200 |
| SUSPICIOUS | 1.0000 | 1.0000 | 1.0000 | 200 |
| BRUTE_FORCE | 1.0000 | 1.0000 | 1.0000 | 200 |

### Confusion matrix (rows=true · cols=pred)

```json
{
  "class_order": [
    "NORMAL",
    "SUSPICIOUS",
    "BRUTE_FORCE"
  ],
  "matrix": [
    [
      200,
      0,
      0
    ],
    [
      0,
      200,
      0
    ],
    [
      0,
      0,
      200
    ]
  ],
  "rows": "actual",
  "columns": "predicted"
}
```

## Validation metrics (all candidates)

| Model | Accuracy | Macro F1 | Min class recall |
|---|---|---|---|
| `logistic_regression_hybrid` | 0.6667 | 0.5556 | 0.0000 |
| `logistic_regression_text` | 0.3333 | 0.3333 | 0.0000 |
| `logistic_regression_behavior` | 0.6667 | 0.5556 | 0.0000 |
| `linear_svm_hybrid` | 0.3333 | 0.2222 | 0.0000 |
| `multinomial_nb_text` | 0.3333 | 0.3333 | 0.0000 |
| `random_forest_behavior` | 0.9967 | 0.9967 | 0.9900 |

## Local artifact locations

- Release: `artifacts/p10/releases/rf-behavior-lab-v1.1.0/`
- Archive: `artifacts/p10/dist/rf-behavior-lab-v1.1.0.tar.gz`
- P8 models: `artifacts/p8/models/`
- P9 eval: `data/evaluation/p9/`
- Metrics JSON: `data/evaluation/p9/test_metrics_selected.json`
- Registry: `artifacts/MODEL_REGISTRY.md`
- Prior release kept: `artifacts/p10/releases/rf-behavior-lab-v1.0.0/`

## Maturity note

CONTROLLED_LAB_VALIDATED on expanded lab-synthetic set. Perfect TEST scores reflect held-out lab scenarios with augmentation within scenario groups — not a production guarantee.
