# P0 — Acceptance Checklist

P0 is complete only if every item below is satisfied.

Legend used in the final P0 report: `PASS` / `FAIL` / `NOT APPLICABLE`.

---

## Checklist

```text
[x] Real problem is clearly defined
[x] Negative impact is documented
[x] Detection scope is limited and explicit
[x] NORMAL is defined
[x] SUSPICIOUS is defined
[x] BRUTE_FORCE is defined
[x] Failed password != automatically brute force
[x] Dataset sources are planned
[x] Dataset schema is defined
[x] Labeling strategy is defined
[x] Data leakage prevention is planned
[x] ML baseline is selected
[x] Evaluation metrics are defined
[x] System architecture is documented
[x] Component responsibilities are separated
[x] Secrets strategy is defined
[x] Mobbin UI dependency is documented
[x] Backend/frontend separation is planned
[x] P1–P12 roadmap exists
[x] No fake ML results exist
[x] No public system is targeted
```

---

## Supporting verification

| Check | Expected evidence |
|---|---|
| Problem vs event distinction | `P0_PROBLEM_DEFINITION.md` §1.2 |
| ODSC + measurable targets marked as initial/unachieved | `P0_PROBLEM_DEFINITION.md` §2 |
| Class definitions consistent | Problem, labeling, ML, architecture docs |
| Hybrid ML plan + LR baseline | `P0_ML_DEFINITION.md` |
| Sources A/B/C + no download in P0 | `P0_DATA_STRATEGY.md` |
| Schema + IP non-memorization | `P0_DATA_SCHEMA.md` |
| Labeling forbids keyword=BRUTE_FORCE | `P0_LABELING_POLICY.md` |
| Scenario-aware splits | `P0_LABELING_POLICY.md` §6 |
| Architecture diagram + SoC | `P0_SYSTEM_ARCHITECTURE.md` |
| Decisions locked | `P0_DECISIONS.md` |
| Roadmap P0–P12 | `PROJECT_ROADMAP.md` |
| Config defaults without secrets | `config/example.yaml` |
| README claims only P0 status | `README.md` |

---

## Explicit non-claims for P0

- Ubuntu Docker test server is **not** implemented/complete in P0
- ML model is **not** trained in P0
- Dashboard is **not** implemented in P0
- Discord alerts are **not** operational in P0
- No accuracy/F1 numbers are presented as achieved results
- No public dataset has been downloaded in P0
