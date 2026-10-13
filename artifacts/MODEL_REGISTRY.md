# BruteWatch local model registry

## Active release

| Field | Value |
|---|---|
| Release ID | `rf-behavior-lab-v1.1.0` |
| Model | `random_forest_behavior` |
| Path | `artifacts/p10/releases/rf-behavior-lab-v1.1.0/` |
| Archive | `artifacts/p10/dist/rf-behavior-lab-v1.1.0.tar.gz` |
| TEST accuracy | 1.0000 |
| TEST macro recall | 1.0000 |
| TEST macro F1 | 1.0000 |
| Metrics doc | `docs/TRAINING_METRICS_rf-behavior-lab-v1.1.0.md` |

## Runtime wiring

- P11 → `artifacts/p10/releases/rf-behavior-lab-v1.1.0`
- P12 → `release_id: rf-behavior-lab-v1.1.0`

## Frozen baselines

| Name | Path |
|---|---|
| P7 original 75 runs | `data/features/p7_baseline_75/` |
| Previous release | `artifacts/p10/releases/rf-behavior-lab-v1.0.0/` |
| Previous P9 | `data/evaluation/p9_archive_v1.0.0/` |


## External large train (online corpora)

| Field | Value |
|---|---|
| Release | `rf-openssh-ext-v1.0.0` |
| Path | `artifacts/external/rf-openssh-ext-v1.0.0/` |
| TEST accuracy | 1.0000 |
| TEST macro recall | 1.0000 |
| TEST macro F1 | 1.0000 |
| Inventory | `docs/EXTERNAL_DATA_INVENTORY.md` |
