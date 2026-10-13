# P3 — Verification Results

**Date:** 2026-09-27  
**Rule:** All PASS values below were observed at runtime.

---

## Lab health

```text
Result: PASS
Evidence: ai-security-ubuntu-lab healthy, 127.0.0.1:2222->22/tcp
```

## Localhost guard

```text
Result: PASS
Evidence: assert_p3_localhost('8.8.8.8') raises; dry-run documents no --host/--target
```

## Safety cap validation

```text
Result: PASS
Evidence:
  attempts=31 rejected (cap 30)
  gap_seconds=0.1 rejected (min 0.25)
```

## Smoke tests

```text
S01: PASS
S02: PASS
B01: PASS
B04: PASS
Batch: P3_SMOKE
```

## Full baseline collection

```text
Batch ID: P3_BASELINE_20260927T071200Z

Suspicious runs attempted: 20
Suspicious runs passed: 20
Suspicious runs failed: 0

Brute-force runs attempted: 25
Brute-force runs passed: 25
Brute-force runs failed: 0

Total SSH auth attempts: 350
Total raw log lines captured: 1440
```

### Per scenario (all 5/5)

```text
S01 S02 S03 S04
B01 B02 B03 B04 B05
```

## Integrity

```text
SHA-256 generation: PASS
Sample checksum verification (all 45 baseline): PASS
Duplicate run ID check: PASS
Index integrity: PASS
No passwords in manifests: PASS
```

## Behavioral sanity (sample)

```text
N06: Failed password count = 1
S01: Failed password count = 3 ; duration ≈ 18.7s ; attempts = 3
B01: Failed password count = 10 ; duration ≈ 35.8s ; attempts = 10
```

These are experimental observations — **not** final detection thresholds.

## P2 regression

```text
P2 dry-run: PASS
P2 N06 smoke after P3: PASS
N06 one-failure rule preserved: PASS (Failed password count = 1)
Lab health after P3: PASS
```

## Matrix

```text
Lab health: PASS
Localhost guard: PASS
Safety cap validation: PASS
Smoke S01/S02/B01/B04: PASS
Full suspicious collection: PASS
Full brute-force collection: PASS
P2 regression: PASS
Index integrity: PASS
Checksum validation: PASS
```
