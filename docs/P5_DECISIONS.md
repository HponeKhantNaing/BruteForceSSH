# P5 Decisions

| Decision | Choice | Reason | Alternatives | Revisit When |
|---|---|---|---|---|
| public data optional | YES — Case B acceptable | Quality > forced merge | Force-download for optics | Stronger labeled host-auth corpus appears |
| official source preference | Official CIC / Loghub / Zenodo only | Avoid unverified mirrors | Kaggle reuploads | Official source unavailable |
| no forced label mapping | Enforced | Prevent anomaly→SUSPICIOUS and attack→BRUTE_FORCE | Heuristic keyword labeling | Documented semantic equivalence exists |
| no public data in local raw | Enforced under `data/external/` | Preserve lab provenance | Mix into `data/raw/` | Never for V1 |
| unlabeled OpenSSH policy | EXTERNAL_UNLABELED_CORPUS | High format match, no GT labels | Invent labels from Failed password | Trusted sequence-level GT published |
| network-flow mismatch policy | EXTERNAL_LABELED_EVALUATION for CIC | Different representation | Direct row merge | Multimodal design explicitly approved |
| license review policy | Document terms; mark uncertain | Public ≠ redistribute freely | Assume OK | Legal clarification for redistribution |
| download staging | Metadata-first; approve required | Avoid multi-GB waste | Full auto-download | download_approved=true + space check |
| large-data guard | No full CIC/CAM download | Domain decision already decisive | Sample-only if needed later | Concrete P6+ experiment needs subset |
| external provenance | Registry + source_snapshot + evaluations | Reproducibility | Undocumented copies | Any future download |
| public IP leakage concerns | Document HIGH/MEDIUM risks | Lab IPs encode attacker identity | Use raw IP as feature | Feature policy with IP mitigations (P7) |
| timestamp leakage concerns | Document CIC day/time windows | Models can learn time=attack | Ignore | Time-aware splits / feature bans |
| direct integration | NONE | No EXACT-compatible public labels | Partial CAM subset | New evidence + mapping file under review |
| HDFS rejection | REJECT | Labeled ≠ relevant | Use as anomaly pretraining | Never for auth supervised V1 |
| SUSPICIOUS coverage | Accept absence in public data | Do not manufacture class | Binary benign/attack remapping | Dataset with intermediate auth behavior |
| P4 immutability | No mutation | P5 evaluates externals only | Relabel with public data | Never |
