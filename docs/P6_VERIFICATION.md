# P6 Verification

Verified: 2026-09-27  
Preprocessing version: `p6-v1`

| Check | Result | Evidence |
|-------|--------|----------|
| P4 source validation | PASS | SHA-256 match; 75 primary runs 30/20/25 |
| P5 external-data guard | PASS | registry dispositions EXTERNAL_ONLY/REJECT; 0 public records |
| Canonical runs | **75** | `canonical_runs.jsonl` |
| Canonical events | **1860** | `canonical_events.jsonl` |
| Logical attempts | **395** | FAILURE 345 + SUCCESS 50 |
| NORMAL | **30** | |
| SUSPICIOUS | **20** | |
| BRUTE_FORCE | **25** | |
| Attempt reconstruction validation | PASS | 75/75 manifest MATCH |
| Leakage guard | PASS | 0 hits |
| Raw immutability | PASS | P4 hashes unchanged after build |
| Deterministic rebuild | PASS | in-memory rebuild == on-disk runs |
| Double-count sanity | PASS | logical failures 345 = AUTH_FAILURE 345 ≠ 345+345 |
| N06 label | PASS | NORMAL; 1 FAILURE + 1 SUCCESS |
| Unit/integration tests | PASS | 14 passed (`tests/test_p6_*.py`) |

## Commands

```bash
python3 scripts/p6_build_dataset.py --dry-run
python3 scripts/p6_build_dataset.py --validate-only
python3 scripts/p6_build_dataset.py --build
python3 scripts/p6_build_dataset.py --report
python3 -m pytest tests/test_p6_*.py -q
```
