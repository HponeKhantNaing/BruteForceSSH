# P4 — Verification Results

**Date:** 2026-09-27  
**Rule:** PASS only when observed.

---

## Index / collection validation

```text
P2 index validation: PASS (34 entries: 30 baseline + 3 smoke + 1 regression)
P3 index validation: PASS (49 entries: 45 baseline + 4 smoke)
```

## Build results

```text
Primary eligible runs: 75
NORMAL: 30
SUSPICIOUS: 20
BRUTE_FORCE: 25

Smoke excluded: 7
Verification/unknown_collection_role excluded: 1
Failed excluded: 0
Interrupted excluded: 0
Checksum mismatches: 0
```

## Critical sanity

```text
N06: AUTH_FAILURE present = YES ; contextual target = NORMAL ; PASS
S01: AUTH_FAILURE present = YES ; contextual target = SUSPICIOUS ; PASS
B01: AUTH_FAILURE present = YES ; contextual target = BRUTE_FORCE ; PASS
```

## Event annotation coverage (primary set)

```text
CONNECTION_EVENT: 840
AUTH_SUCCESS: 50
SESSION_OPEN: 50
SESSION_CLOSE: 50
OTHER_AUTH: 140
PAM_AUTH_FAILURE: 345
AUTH_FAILURE: 345
UNCLASSIFIED: 40
INVALID_USER: 0
```

## Integrity / tests

```text
Checksum verification: PASS
Index-manifest consistency: PASS
Duplicate run check: PASS
Raw immutability: PASS
Deterministic rebuild: PASS
pytest (11 tests): PASS
```

## Matrix

```text
P2 validation                  PASS
P3 validation                  PASS
Manifest validation            PASS
Checksum validation            PASS
Scenario mapping               PASS
N06 special-case test          PASS
S01 test                       PASS
B01 test                       PASS
Event role parsing             PASS
Smoke exclusion                PASS
Failed-run exclusion           PASS
Duplicate handling             PASS
Raw immutability               PASS
Deterministic rebuild          PASS
Regression                     PASS
```
