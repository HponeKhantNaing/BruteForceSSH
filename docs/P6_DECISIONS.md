# P6 Decisions

| Decision | Choice | Reason | Alternatives | Revisit When |
|---|---|---|---|---|
| local P4 data only | enforced | P5 Case B — no direct integration | Merge public data | New INCLUDE_CANDIDATE appears |
| no public supervised merge | `enabled: false` | Domain/label incompatibility | External eval only | Multimodal redesign |
| run = contextual sample | preserved | Matches P4 policy | Line-level labels | Never for V1 |
| event != attempt | enforced | PAM double-count risk | Count every failure line | Never |
| PAM/Auth failure correlation | same sshd PID pairing | Observed OpenSSH behavior | Time-only windows | Format changes |
| pseudonymous source IDs | SRC_### | Relational grouping without IP memorization | Drop source entirely | Feature policy needs change |
| pseudonymous user IDs | USR_### | Unique-user counts without plaintext | Hash usernames | Privacy review |
| dynamic token normalization | IP/PORT/PID/USER/HOST | Prevent shortcuts | Keep raw tokens | Parser robustness study |
| raw immutability | read-only raw/P4/P5 | Provenance | In-place clean | Never |
| noise marked not deleted | OTHER_AUTH/UNCLASSIFIED | Auditability | Hard delete | Confirmed junk corpus |
| scenario metadata excluded from text | enforced | Label leakage | Include scenario tokens | Never |
| deterministic build | sorted IDs + stable ordering | Reproducibility | Random UUIDs | Never |
| no class balancing | preserve 30/20/25 | Honest distribution | SMOTE/oversample | P8 training policy |
| no train/test split | metadata only | P7/P8 owns splits | Emit train.csv | P7 |
| lowercase normalized_message | yes | TF-IDF consistency | Preserve case | Ablation study |
| CONNECTION_EVENT not attempt | yes | Not an auth outcome | Count connections | Behavior redesign |
| session lines not extra attempts | attach to SUCCESS | Auth outcome is Accepted password | Separate attempts | Evidence changes |
