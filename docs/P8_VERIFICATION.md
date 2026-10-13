# P8 Verification

Verified: 2026-09-27  
Training version: `p8-v1`

| Check | Result |
|-------|--------|
| P7 validation | PASS |
| Scenario-group split | PASS |
| Scenario overlap | **0** |
| Train samples | **45** (N20 / S10 / B15) |
| Validation samples | **15** (N5 / S5 / B5) |
| Test samples | **15** (N5 / S5 / B5) |
| TF-IDF fit scope | **TRAIN ONLY** |
| TF-IDF vocabulary | **44** |
| Behavior features | **22** |
| Scaler fit scope | **TRAIN ONLY** |
| Hybrid feature dimension | **66** (44+22) |
| Logistic hybrid | TRAINED |
| Logistic text | TRAINED |
| Logistic behavior | TRAINED |
| LinearSVM hybrid | TRAINED |
| MultinomialNB text | TRAINED |
| RandomForest behavior | TRAINED |
| Test metrics computed | **NO** |
| Artifact round-trip | PASS |
| Leakage audit | PASS |
| Unit tests | **13 passed** |

## Commands

```bash
python3 scripts/p8_train_models.py --dry-run
python3 scripts/p8_train_models.py --validate-only
python3 scripts/p8_train_models.py --split
python3 scripts/p8_train_models.py --train
python3 scripts/p8_train_models.py --report
python3 -m pytest tests/test_p8_*.py -q
```
