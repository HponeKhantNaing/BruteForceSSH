# P7 Verification

Verified: 2026-09-27  
Feature engineering version: `p7-v1`

| Check | Result |
|-------|--------|
| P6 validation | PASS |
| Samples | **75** |
| Behavioral feature rows | **75** |
| Text rows | **75** |
| Target rows | **75** |
| Default behavioral feature count | **22** |
| Constant features | **[]** (none) |
| Near-constant features | unique_users_total, unique_users_60s_max, has_multiple_attempts, success_after_failure, first_attempt_failed, last_attempt_success |
| TF-IDF fitted | **NO** |
| Text leakage | PASS |
| Numeric leakage | PASS |
| Sample alignment | PASS |
| Non-finite values | **0** |
| P6 immutability | PASS |
| Deterministic rebuild | PASS (validate == build alignment) |
| Unit tests | **12 passed** (`tests/test_p7_*.py`) |

## Commands

```bash
python3 scripts/p7_build_features.py --dry-run
python3 scripts/p7_build_features.py --validate-only
python3 scripts/p7_build_features.py --build
python3 scripts/p7_build_features.py --report
python3 -m pytest tests/test_p7_*.py -q
```
