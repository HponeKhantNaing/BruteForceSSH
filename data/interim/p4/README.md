# P4 interim labeling outputs

Derived artifacts only. **Raw evidence under `data/raw/` is immutable.**

## Files

| File | Meaning |
|---|---|
| `run_labels.jsonl` | One contextual ML target per eligible verified scenario run |
| `event_annotations.jsonl` | Atomic event roles per raw log line (no threat class) |
| `excluded_runs.jsonl` | Runs not accepted into the primary candidate set |
| `class_distribution.json` | Run-level class counts (not line counts) |
| `labeling_report.json` | Build summary |
| `audit/label_audit.jsonl` | Traceability for accepted labels |

## Important

- `target_label` lives only on **run** records.
- `event_role` (e.g. `AUTH_FAILURE`) is **not** `BRUTE_FORCE`.
- Rebuild safely with: `python3 scripts/p4_build_labels.py --build`

No cleaning, feature engineering, or model training is performed here.
