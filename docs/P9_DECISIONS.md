# P9 Decisions

| Decision | Choice | Reason | Alternatives | Revisit When |
|---|---|---|---|---|
| validation-only model selection | enforced | Protect TEST | TEST ranking | Never |
| macro F1 primary metric | yes | All three classes matter | Accuracy-only | Metric policy change |
| minimum-class-recall tie-break | yes | Avoid ignoring a class | Prefer hybrid always | Preference update |
| selected model only on TEST | enforced | One-shot final estimate | Evaluate all on TEST | Never |
| one-time TEST lock | receipt | Prevent peeking cycles | Allow re-test | New evaluation version |
| no refitting in P9 | enforced | Evaluate frozen artifacts | Retrain on train+val | Explicit new phase |
| no hyperparameter tuning | enforced | Would invalidate freeze | Grid search | Future versioned study |
| no threshold tuning | enforced | Same | Threshold search | Calibrated deployment study |
| no probability calibration | enforced | Creates new model | CalibratedClassifierCV | Separate phase |
| no test-based model change | enforced | Honest reporting | Switch after TEST | Never |
| scenario-level interpretation | required | Class = one scenario | Ignore scenarios | Larger multi-scenario holdouts |
| quality label | descriptive | Small-n caution | Hard production gate | Defined SLO exists |
