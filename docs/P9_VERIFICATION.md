# P9 Verification

Verified: 2026-09-27  
Evaluation version: `p9-v1`

| Check | Result |
|-------|--------|
| P8 artifact integrity | PASS |
| P8 split hash | `4eea4313ef253b354464c43e525055a10e250fedf25f0b13e22d48cfc94eb442` |
| Validation models evaluated | **6** |
| Validation samples | **15** |
| Model selected | `random_forest_behavior` |
| Selection policy | validation macro F1 (+ tie-breaks) |
| Selection lock | PASS |
| Test models evaluated | **1** |
| Expected test models evaluated | 1 |
| Test samples | **15** |
| Test receipt | PASS |
| P9 fit operations | **0** |
| Leakage audit | PASS |
| P8 artifacts unchanged | PASS |
| Second TEST attempt | REFUSED |
| Unit tests | **12 passed** |

## Commands

```bash
python3 scripts/p9_evaluate_models.py --dry-run
python3 scripts/p9_evaluate_models.py --validate-only
python3 scripts/p9_evaluate_models.py --evaluate-validation
python3 scripts/p9_evaluate_models.py --select-model
python3 scripts/p9_evaluate_models.py --evaluate-test-selected
python3 scripts/p9_evaluate_models.py --report
python3 -m pytest tests/test_p9_*.py -q
```
