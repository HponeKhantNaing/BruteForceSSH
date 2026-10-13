# Project Roadmap (P0 → P12)

**Project:** AI-Based Real-Time Server Log Threat Detection and Alert System  
**Rule:** Implement only the current authorized phase. Do not skip ahead and claim later phases complete.

```text
P0  Problem Definition / Architecture / Detection Scope / Dataset Strategy / ML Strategy
P1  Ubuntu Docker Test Server
P2  Normal Log Collection
P3  Controlled Suspicious / Attack Scenario Collection
P4  Labeling Pipeline
P5  Public Dataset Evaluation / Integration
P6  Cleaning + Preprocessing + Dataset Build
P7  Feature Engineering
P8  ML Training
P9  Model Evaluation
P10 Model Export / Versioning
P11 Real-Time ML Monitoring Integration
P12 Dashboard + Discord Alert + End-to-End Demo
```

---

## P0 — Project Foundation

| | |
|---|---|
| **Objective** | Define the real problem, detection scope, classes, data/ML strategy, architecture, and acceptance criteria without implementing the detector |
| **Inputs** | Project brief; lab-only security constraint; planned Mobbin UI later |
| **Actions** | Write P0 docs; create config example; create folder skeleton; lock decisions |
| **Deliverables** | Docs under `docs/`; `config/example.yaml`; README; `.env.example`; `.gitignore`; empty module dirs |
| **Success Criteria** | Ambiguity removed; checklist passes; no fake ML results; no third-party attack design |
| **Depends on** | None |

---

## P1 — Ubuntu Docker Test Server

| | |
|---|---|
| **Objective** | Provide an isolated, project-owned Ubuntu server for authorized auth-log experiments |
| **Inputs** | P0 architecture; Docker/Compose plan; Apple Silicon compatibility awareness |
| **Actions** | Define container image/Compose service; enable SSH/auth logging suitable for collection; document how to start/stop |
| **Deliverables** | `ubuntu-server/` assets; `docker-compose.yml` service; runbook notes |
| **Success Criteria** | Container starts locally; auth events can be produced against this host only; reproducible on macOS+Docker |
| **Depends on** | P0 |

---

## P2 — Normal Log Collection

| | |
|---|---|
| **Objective** | Collect realistic normal authentication activity from the lab server |
| **Inputs** | Running P1 server; collector design |
| **Actions** | Perform legitimate logins/session activity; capture raw logs; store under `data/raw/` with scenario ids |
| **Deliverables** | Normal-scenario raw logs; collection notes |
| **Success Criteria** | Raw logs contain successes/session events and isolated failures without attack intent; `data_source=local_lab` |
| **Depends on** | P1 |

---

## P3 — Controlled Suspicious / Attack Scenario Collection

| | |
|---|---|
| **Objective** | Generate authorized suspicious and brute-force-like authentication behavior **only** against the lab server |
| **Inputs** | P1 server; P2 collection method |
| **Actions** | Run controlled scenarios (elevated failures, multi-username attempts, bursts); save raw logs with scenario metadata |
| **Deliverables** | Suspicious and brute-force scenario raw logs; scenario manifests |
| **Success Criteria** | Scenarios are reproducible; clearly separated from normal collection; no external targets |
| **Depends on** | P1, P2 |

---

## P4 — Labeling Pipeline

| | |
|---|---|
| **Objective** | Assign `NORMAL` / `SUSPICIOUS` / `BRUTE_FORCE` using the labeling policy |
| **Inputs** | Raw scenarios; `P0_LABELING_POLICY.md` |
| **Actions** | Implement/assist labeling workflow; attach `scenario_id`; ban keyword-only brute-force labels |
| **Deliverables** | Labeled interim dataset; labeling notes for edge cases |
| **Success Criteria** | Isolated failures can be `NORMAL`; brute-force requires behavioral evidence; schema fields populated |
| **Depends on** | P2, P3 |

---

## P5 — Public Dataset Evaluation / Integration

| | |
|---|---|
| **Objective** | Evaluate whether any public dataset is compatible as supplementary data |
| **Inputs** | Candidate public datasets (downloaded only in this phase if approved); license/format checks |
| **Actions** | Review license, labels, auth relevance, domain mismatch; accept/reject with written rationale; integrate only if aligned |
| **Deliverables** | Evaluation memo; optional supplementary data marked `public:<name>` |
| **Success Criteria** | No blind merges; incompatibilities documented; local lab remains primary |
| **Depends on** | P0 data strategy; preferably P4 schema familiarity |
| **Status** | **Complete (Case B)** — Loghub OpenSSH = EXTERNAL_UNLABELED_CORPUS; CIC-IDS2017 & CAM-LDS = EXTERNAL_LABELED_EVALUATION; no DIRECT_INTEGRATION_CANDIDATE; P4 remains primary supervised source |

---

## P6 — Cleaning + Preprocessing + Dataset Build

| | |
|---|---|
| **Objective** | Build processed datasets ready for features/training |
| **Inputs** | Labeled interim data; schema |
| **Actions** | Clean text; validate types; create processed tables; write scenario-aware split manifests |
| **Deliverables** | `data/processed/` artifacts; split manifest |
| **Success Criteria** | No train/test scenario leakage; synthetic rows remain marked; schema compliance |
| **Depends on** | P4 (and P5 if used) |
| **Status** | **Complete** — local P4 only (75 runs); logical attempts reconstructed; no public supervised merge; outputs under `data/processed/p6/` |

---

## P7 — Feature Engineering

| | |
|---|---|
| **Objective** | Implement hybrid text + behavioral feature pipeline |
| **Inputs** | Processed events; window config |
| **Actions** | Compute rolling features; build TF-IDF inputs; verify IP memorization mitigations |
| **Deliverables** | Feature pipeline code; feature documentation updates |
| **Success Criteria** | Features match schema; windows configurable; unit tests for aggregates |
| **Depends on** | P6 |
| **Status** | **Complete** — 75 aligned samples; 22 default behavioral features; TF-IDF unfitted; outputs under `data/features/p7/` |

---

## P8 — ML Training

| | |
|---|---|
| **Objective** | Train baseline Logistic Regression (+ optional comparisons) offline |
| **Inputs** | Feature-ready train/validation splits |
| **Actions** | Fit models; tune lightly if needed; keep experiments reproducible |
| **Deliverables** | Trained candidate models (not yet final export ceremony) |
| **Success Criteria** | Training completes on laptop without GPU; class predictions produced on validation scenarios |
| **Depends on** | P7 |
| **Status** | **Complete** — scenario-group 45/15/15 split; TRAIN-only TF-IDF/scaler; 6 experimental models; TEST locked; no winner |

---

## P9 — Model Evaluation

| | |
|---|---|
| **Objective** | Measure real performance without fabricated metrics |
| **Inputs** | Held-out scenarios; trained candidates |
| **Actions** | Compute Accuracy, Precision, Recall, F1, Confusion Matrix, per-class metrics; analyze FP/FN |
| **Deliverables** | Evaluation report with real numbers |
| **Success Criteria** | Metrics reported honestly; leakage checks described; baseline chosen for export |
| **Depends on** | P8 |
| **Status** | **Complete** — validation selected `random_forest_behavior`; locked TEST 15/15 on 3 scenarios; no production claim |

---

## P10 — Model Export / Versioning

| | |
|---|---|
| **Objective** | Save the selected model and metadata for inference |
| **Inputs** | Chosen model from P9 |
| **Actions** | Export vectorizer/model; record version, training date, class list, feature list |
| **Deliverables** | Artifacts under `models/`; version notes |
| **Success Criteria** | Fresh process can load artifacts and predict without retraining |
| **Depends on** | P9 |
| **Status** | **Complete** — `rf-behavior-lab-v1.0.0` packages exact P9-selected RF behavior (raw); no TF-IDF/scaler; immutable + checksummed |

---

## P11 — Real-Time ML Monitoring Integration

| | |
|---|---|
| **Objective** | Connect live lab logs to inference without UI dependency |
| **Inputs** | P1 logs; P10 artifacts; architecture wiring |
| **Actions** | Implement monitor loop: collect → parse → windows → features → infer → event store |
| **Deliverables** | Working monitoring service; structured detection events |
| **Success Criteria** | Live events scored with latency suitable for demo; engine independent from dashboard |
| **Depends on** | P1, P10 |
| **Status** | **Complete** — 75/75 feature parity; 345/50 attempt parity; per-source episodes; live E2E; no Discord/dashboard |

---

## P12 — Dashboard + Discord Alert + End-to-End Demo

| | |
|---|---|
| **Objective** | Present detections via Mobbin-inspired UI and optional Discord alerts |
| **Inputs** | P11 event stream/API; Mobbin reference from user; webhook env |
| **Actions** | Implement API+frontend against contract; alert policy; end-to-end demo script |
| **Deliverables** | Dashboard; Discord integration; demo runbook |
| **Success Criteria** | UI consumes structured events only; Discord alerts follow policy; full lab demo works |
| **Depends on** | P11; Mobbin reference availability for final UI |
| **Status** | **Complete** — Flask localhost dashboard; SQLite outbox; `p12-alert-v1` final-non-normal; CONTROLLED-LAB V1 |

---

## Status snapshot

| Phase | Status |
|---|---|
| P0 | Complete (foundation docs) |
| P1 | Complete (Ubuntu Docker SSH lab + host auth log) |
| P2 | Complete (normal/benign auth scenario collection) |
| P3 | Complete (controlled suspicious / brute-force-like collection) |
| P4 | Complete (ground-truth labeling: run targets + event roles) |
| P5 | Complete (public dataset evaluation Case B — no direct supervised integration) |
| P6 | Complete (canonical local dataset; no public supervised merge) |
| P7 | Complete (behavioral + text feature sources; TF-IDF unfitted) |
| P8 | Complete (scenario-safe split + TRAIN-only models; TEST locked) |
| P9 | Complete (validation selection + one-time TEST; RF behavior selected) |
| P10 | Complete (lab release `rf-behavior-lab-v1.0.0`; CONTROLLED_LAB_VALIDATED) |
| P11 | Complete (realtime monitor; feature+attempt parity; live E2E) |
| P12 | Complete (dashboard + Discord outbox; CONTROLLED-LAB V1) |
