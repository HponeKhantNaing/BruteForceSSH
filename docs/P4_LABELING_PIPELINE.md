# P4 — Ground-Truth Labeling Pipeline

**Phase:** P4  
**Depends on:** Verified P2 + P3 controlled collections  
**Status:** Implemented and verified (see `P4_VERIFICATION.md`)

---

## Objective

Convert verified P2/P3 experimental provenance into an auditable labeling layer:

```text
Raw Evidence
+ Scenario Provenance
+ Manifest Ground Truth
+ Integrity Verification
+ Explicit Label Policy
        ↓
Auditable Ground-Truth Labels
```

---

## Why run-level context matters

Brute-force and suspicious behavior are **multi-event**. Labeling each line `BRUTE_FORCE` because it says `Failed password` would mislabel N06 and teach keyword shortcuts.

---

## Why failed password ≠ threat label

```text
event_role: AUTH_FAILURE
parent run target: NORMAL | SUSPICIOUS | BRUTE_FORCE
```

All three are possible. The contextual run target comes from verified scenario intent, not keywords.

---

## Sample unit

**Initial ML target unit:** one verified scenario run / contextual authentication sequence.

---

## Atomic event roles

```text
AUTH_SUCCESS
AUTH_FAILURE
INVALID_USER
PAM_AUTH_FAILURE
SESSION_OPEN
SESSION_CLOSE
CONNECTION_EVENT
OTHER_AUTH
UNCLASSIFIED
```

These are roles, not threat classes.

---

## Contextual target classes

```text
NORMAL
SUSPICIOUS
BRUTE_FORCE
```

---

## P2 / P3 mapping

| Intent | Target |
|---|---|
| `normal` | `NORMAL` |
| `suspicious` | `SUSPICIOUS` |
| `brute_force` | `BRUTE_FORCE` |

### N06 special case

`N06_ISOLATED_PASSWORD_MISTAKE` → contextual **`NORMAL`**, even though it contains `AUTH_FAILURE`.

---

## Eligibility policy

Accept only when:

- index + manifest + raw log present
- result = success
- SHA-256 matches
- scenario known + intent consistent
- collection_role = baseline (default)
- optional ground-truth checks pass

---

## Smoke run policy

Default: **exclude** smoke and verification/regression batches from the primary candidate set.

---

## Exclusion policy

Excluded runs are recorded in `excluded_runs.jsonl` with reason codes. Raw files are never deleted.

---

## Integrity verification

Recomputed SHA-256 must match manifests. Index/manifest conflicts cause exclusion.

---

## Audit trail

`audit/label_audit.jsonl` records mapping rule, checksum verification, batch, and paths for each accepted run.

---

## Leakage protection metadata

Run labels include:

```text
split_group_run
split_group_batch
split_group_scenario
```

P4 does **not** create train/test splits.

---

## Limitations

- Contextual run labels ≠ production traffic units
- Event parser is intentionally minimal
- Class counts are run-level, not line-level
- Lab data has limited IP/user diversity
- No cleaning / features / models yet

---

## Commands

```bash
python3 scripts/p4_build_labels.py --dry-run
python3 scripts/p4_build_labels.py --validate-only
python3 scripts/p4_build_labels.py --build
python3 scripts/p4_build_labels.py --report
```

---

## P5 / P6 handoff

| Artifact | Path |
|---|---|
| Run labels | `data/interim/p4/run_labels.jsonl` |
| Event annotations | `data/interim/p4/event_annotations.jsonl` |
| Exclusions | `data/interim/p4/excluded_runs.jsonl` |
| Distribution | `data/interim/p4/class_distribution.json` |
| Report | `data/interim/p4/labeling_report.json` |

P5 evaluates public data separately. P6 joins raw logs + P4 labels into a cleaned dataset.
