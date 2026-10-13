# P0 — Decision Log

**Phase:** P0 — Project Foundation  
**Rule:** Future phases must not silently change these decisions. If a change is required, document why in that phase and add a new row here.

---

## Locked decisions

| Decision | Choice | Reason | Alternatives | Revisit When |
|---|---|---|---|---|
| Problem domain | Authentication / login threat monitoring from server logs | Matches real admin pain: high-volume auth events, weak keyword signals | Full SIEM; network IDS; malware sandbox | Scope expansion beyond university V1 demo |
| Detection scope (V1) | Auth/login activity only on project-owned lab server | Keeps project feasible and ethically constrained | Multi-log-source correlation; host IDS | After V1 demo succeeds and new requirements appear |
| Class labels | `NORMAL`, `SUSPICIOUS`, `BRUTE_FORCE` | Separates routine mistakes from attention-needed and confirmed brute patterns | Binary malicious/benign; more MITRE-mapped classes | If label confusion stays high after P3–P9 |
| Failed password policy | Not automatically `BRUTE_FORCE` | One mistype ≠ attack | Keyword alerts | Never reverse without explicit evidence policy change |
| ML problem type | Hybrid supervised classification (text + behavioral) | Brute force is multi-event behavior | Text-only; pure anomaly detection; DL sequence models | If hybrid underperforms held-out scenarios |
| Text features | TF-IDF on `clean_log` | Lightweight, sparse, laptop-friendly | Bag-of-words counts; embeddings | If text channel adds little value vs behavior-only |
| Behavioral features | 30s/60s/5m failure counts, successes, unique users, rate, gap, failure ratio | Captures burst and spray patterns | Longer windows; graph features | After baseline feature ablation in P7–P9 |
| Baseline ML model | Logistic Regression (+ TF-IDF) | Fast, interpretable, no GPU, good sparse baseline | NB / RF / Linear SVM as comparisons; deep learning later | If LR cannot separate classes after solid features |
| Comparison models | Naive Bayes, Random Forest, Linear SVM | Cheap ablations for a student project | XGBoost; neural nets | P8–P9 experiments |
| Deep learning in V1 | No (unless later justified) | Complexity, data size, reproducibility | LSTM/Transformer log models | Measurable need + enough data |
| Training location | Local offline training | Reproducible student workflow; no cloud requirement | Cloud training jobs | Only if local resources become insufficient |
| Inference mode | Online scoring with pre-exported artifacts | Separates train from monitor | Online learning / continuous refit | Concept drift becomes a measured problem |
| Test environment | Docker Ubuntu lab server (project-owned) | Authorized, reproducible, isolated | Bare-metal VM only; remote cloud VPS | Portability issues on Apple Silicon / Docker |
| Alert destination | Discord webhook (optional, env-configured) | Simple demo alerting channel | Email; Slack; PagerDuty | If Discord unsuitable for assessors |
| Who decides “attack” | Detection engine + policy — **not** Discord | Alerts are outputs | Alert tool as classifier | Never |
| Dashboard approach | Backend API + later Mobbin-inspired frontend | UI can change without engine redesign | Monolithic server-rendered pages with embedded logic | If API contract needs versioning |
| UI design in P0 | Explicitly deferred | User will supply Mobbin reference | Inventing a final UI now | When Mobbin reference is provided (P12) |
| Secrets | Env vars (e.g. `DISCORD_WEBHOOK_URL`); never commit | Prevent credential leakage | Hardcoded webhooks | Always |
| GPU | Not required | LR baseline + laptop demo | CUDA stacks | Only for optional future DL |
| Cloud infrastructure | Not required for V1 core path | Keep project local and free | Managed cloud SIEM | Institution requirements change |
| Paid services | None required for core path | University project constraints | Paid APIs | Avoid unless unavoidable |
| Data sources | Local lab primary; synthetic marked; public optional after review | Control + ethics + format fit | Public-only datasets | P5 evaluation outcomes |
| Split strategy | Scenario-aware (`scenario_id`) splits | Prevent session leakage | Random row splits | Never prefer random-only for final claims |
| IP usage | Grouping/display allowed; raw IP not a malice meme feature | Prevent memorizing lab addresses | IP one-hot as feature | If leakage suspected in error analysis |

---

## Change protocol

1. Propose the change in the relevant phase doc.
2. Explain why evidence justifies leaving the P0 choice.
3. Add a dated amendment row to this table.
4. Update dependent docs (`README`, schema, architecture) for consistency.
