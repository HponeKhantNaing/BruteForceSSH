# P2 — Verification Results

**Date:** 2026-09-27  
**Rule:** Values below were observed at runtime. No fabricated counts.

---

## Lab health

```text
Result: PASS
Evidence: ai-security-ubuntu-lab Up (healthy), 127.0.0.1:2222->22/tcp
```

## Credential validation

```text
Result: PASS
Evidence: single successful Paramiko session before collection; no retry loop
```

## Localhost guard

```text
Result: PASS
Evidence: assert_localhost('8.8.8.8') raises RuntimeError
```

## Smoke test

```text
N01 ×1  PASS
N02 ×1  PASS
N06 ×1  PASS
N06 Failed password count: 1
N06 Accepted password count: 1
```

## Full baseline batch

```text
Batch ID: P2_BASELINE_20260927T070000Z
Runs attempted: 30
Runs passed: 30
Runs failed: 0
Total raw log lines captured: 420
```

### Per scenario

| Scenario | Attempted | Passed | Failed |
|---|---:|---:|---:|
| N01_SINGLE_SUCCESS | 5 | 5 | 0 |
| N02_COMMAND_SESSION | 5 | 5 | 0 |
| N03_SHORT_SESSION | 5 | 5 | 0 |
| N04_LOW_FREQUENCY_REPEAT | 5 | 5 | 0 |
| N05_SESSION_RECONNECT | 5 | 5 | 0 |
| N06_ISOLATED_PASSWORD_MISTAKE | 5 | 5 | 0 |

## N06 safety

```text
Intentional failed attempts per run: 1
Unexpected authentication retries: 0
Recovery login result: PASS
Attack-like burst detected: NO
```

All 5 baseline N06 runs had exactly one `Failed password` line in the captured slice.

## Integrity

```text
SHA-256 generation: PASS
Sample checksum re-verification (all 30 baseline runs): PASS
Duplicate run ID check: PASS (0 duplicates across index)
Index integrity: PASS (no orphan paths)
Password absent from manifests/index: PASS
```

## P1 regression

```text
Result: PASS
Evidence: container remained healthy; post-collection SSH success OK
```

## Matrix

```text
Lab health                    PASS
Credential validation         PASS
Localhost guard               PASS
N01                           PASS
N02                           PASS
N03                           PASS
N04                           PASS
N05                           PASS
N06                           PASS
Scenario boundary capture     PASS
Manifest creation             PASS
Global index                  PASS
Checksum validation           PASS
Raw data gitignore            PASS
P1 regression                 PASS
```
