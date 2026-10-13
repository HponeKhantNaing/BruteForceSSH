# P11 Decisions

| Decision | Choice | Reason | Alternatives | Revisit When |
|---|---|---|---|---|
| Reuse P6/P7 semantics | Call `reconstruct_attempts` + `compute_behavior_features` | Train-serving parity | Reimplement formulas | Feature contract MAJOR |
| Per-source episode grouping | `group_by: source` | Preserve multi-user features | Per-user / global | New threat model |
| TRAIN-only context timeout | idle=30s from TRAIN max gap≈15.56s | Avoid TEST leakage | Fixed arbitrary timeout | New TRAIN timing |
| Bounded max episode duration | 300s | Align with P7 5m horizon | Unbounded | Longer lab sessions |
| ACTIVE_PREFIX provisional | `provisional: true` | Prefix ≠ full-run training dist | Final-only inference | Calibration study |
| EPISODE_FINAL final snapshot | `final: true` | Closer to bounded run | Always provisional | P12 alert policy |
| Predict per logical attempt | Not per raw line | Avoid PAM double inference | Line-level predict | N/A |
| No scaler / No TF-IDF | Behavior-raw RF only | Matches P10 contract | Hybrid model release | Model reselection |
| No online learning | fit/partial_fit blocked | Frozen release | Online updates | Explicit V2 |
| No prevention / alerting | Emit events only | P12 owns policy | Inline Discord | P12 |
| Runtime identities not persisted | `SRC_RUNTIME_*` / `USR_RUNTIME_*` | Privacy | Persist hashed IPs | Compliance needs |
