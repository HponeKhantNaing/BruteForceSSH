# P4 — Decision Log

| Decision | Choice | Reason | Alternatives | Revisit When |
|---|---|---|---|---|
| Contextual run as ML target unit | Verified scenario run | Behavior is multi-event | Line-level threat labels | Windowed samples in P6/P7 |
| Event role vs target separation | Two layers | Prevent keyword shortcuts | Single label column | Never merge roles into threat classes |
| N06 remains NORMAL | Explicit policy + check | Isolated mistake ≠ attack | Relabel as SUSPICIOUS | Evidence shows misuse |
| Scenario intent mapping | normal→NORMAL, suspicious→SUSPICIOUS, brute_force→BRUTE_FORCE | Controlled ground truth | Keyword heuristics | New scenario families |
| Smoke exclusion | Default exclude | Keep primary set clean | Include via `--include-smoke` | Need smoke in training |
| Failed/interrupted exclusion | Exclude | Incomplete evidence | Soft include | Never for primary |
| Checksum requirement | Mandatory for accept | Integrity | Trust manifests only | Never |
| Raw immutability | Read-only raw | Evidence preservation | In-place edits | Never |
| Unknown scenario exclusion | Exclude | No guessing | Name-based inference | New allow-list entries |
| No guessed labels | Strict allow-list | Auditability | Fuzzy mapping | Never |
| No class balancing in P4 | Report only | Labeling ≠ resampling | SMOTE etc. | P8 if needed |
| Split-group metadata | run/batch/scenario fields | Future leakage prevention | Random split now | P6 splits |
| Annotation raw text | Path + line_number only | Minimize duplication | Store raw_line | Audit needs text |
| Verification batches | Exclude like non-baseline | Regression is not baseline | Include | Explicit policy change |
