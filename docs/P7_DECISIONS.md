# P7 Decisions

| Decision | Choice | Reason | Alternatives | Revisit When |
|---|---|---|---|---|
| run-level sample unit | 1 run = 1 sample | Matches P4/P6 semantics | Line/attempt samples | Never for V1 |
| canonical_attempts as behavioral source | enforced | Avoids PAM double-count | Event-role counts | Never |
| unfitted TF-IDF in P7 | enforced | Prevent test leakage | Fit on all data | Never |
| 15–20 feature budget | ~22 defaults | Small-n safety | Hundreds of features | More data |
| rolling-window max semantics | inclusive [t−W,t] | Online-compatible | Half-open | Policy change |
| no source identity feature by default | diagnostic only | Constant SRC_001 | Use SRC as feature | Multi-source data |
| no event double-counting | logical attempts | P6 contract | Sum failure roles | Never |
| no supervised feature selection | deferred to P8/P9 | Uses targets | Chi2/MI now | After split |
| no balancing | preserve 30/20/25 | Honest data | SMOTE | P8 policy |
| no split | metadata only | P8 owns splits | Random split now | P8 |
| train-serving parity | history-only API | P11 reuse | Batch-only formulas | Streaming design |
| text length not default feature | diagnostic | Correlates with attempts | Add length feature | Ablation |
| near-constant kept enabled | yes | Still informative binary flags | Auto-disable | P9 |
| duration fallback | started/ended/sequence | Some P6 durations null | Drop samples | Schema fix |
| failures_before_first_success if no success | = failed_attempts | Deterministic | Use −1/NaN | Convention change |
