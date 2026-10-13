# P0 — ML Problem Definition, Baseline Models & Evaluation

**Phase:** P0 — Project Foundation  
**Status:** Planning only — **no model training in P0**  
**Output classes:** `NORMAL` | `SUSPICIOUS` | `BRUTE_FORCE`

---

## 1. What kind of ML problem is this?

Version 1 uses a **hybrid feature-based supervised classification** approach.

| Approach | Role in V1 |
|---|---|
| Text classification | Partial — TF-IDF on cleaned log messages |
| Anomaly detection | Not primary in V1 |
| Behavioral classification | Essential — rolling-window numeric features |
| **Hybrid (selected)** | Text features + behavioral features → multi-class classifier |

### Why not text-only classification?

Brute-force and suspicious login activity are primarily **multi-event behaviors**. A single line such as:

```text
Failed password for invalid user admin from 172.18.0.5
```

can appear in both:

- an isolated user mistake (`NORMAL`), and
- a high-rate password spray (`BRUTE_FORCE`)

Text alone lacks rate, burst, and multi-username context. Behavioral features supply that context.

### Why not pure anomaly detection in V1?

Anomaly detection is useful later for unknown patterns, but Version 1 needs:

- explicit labels for controlled scenarios
- clear class definitions for evaluation
- interpretable student-project baselines

Supervised hybrid classification fits that need first.

---

## 2. ML Pipeline (Version 1)

```text
Raw Authentication Log
        +
Behavioral Features
        ↓
 Feature Pipeline
        ↓
ML Classifier
        ↓
NORMAL / SUSPICIOUS / BRUTE_FORCE
```

### Online path (future real-time)

```text
Parsed event
   ↓
Rolling window update (per source_id)
   ↓
Feature vector (text + numeric)
   ↓
Loaded trained model
   ↓
Class + confidence
   ↓
Event store / Alert manager / Dashboard API
```

### Offline path (future training)

```text
Labeled dataset (scenario-aware)
   ↓
Train / validation / test split by scenario_id
   ↓
Fit vectorizer + classifier
   ↓
Evaluate → export artifacts to models/
```

**Separation rule:** Training code must **not** run every time real-time monitoring starts.

---

## 3. Feature Plan

### 3.1 Text features

- Cleaned log message (`clean_log`)
- TF-IDF vectorization (sparse)

Planned cleaning (future P6/P7 — not implemented in P0):

- lowercase
- strip volatile identifiers where appropriate for text (while keeping structured fields separately)
- normalize whitespace
- optionally mask literal IPs/usernames in the *text* channel to reduce memorization (structured fields remain available for windowing)

### 3.2 Behavioral / numeric features

| Feature | Meaning |
|---|---|
| `failed_count_30s` | Failed auth attempts for source in last 30s |
| `failed_count_60s` | Failed auth attempts for source in last 60s |
| `failed_count_5m` | Failed auth attempts for source in last 5 minutes |
| `success_count_5m` | Successful auths for source in last 5 minutes |
| `unique_users_60s` | Distinct usernames attempted by source in last 60s |
| `attempt_rate` | Attempts per second over the medium window |
| `time_since_previous_attempt` | Seconds since previous attempt from same source |
| `failure_ratio` | Failures / (failures + successes) in long window |

These features exist so the model can distinguish isolated failures from bursty multi-user probing.

### 3.3 What must not be a raw ML memorization signal

Do **not** train the model to memorize:

```text
192.168.x.x = malicious
```

Source IP / `source_id` may be used to **group** events for window features, but the raw IP string should not be treated as a privileged class indicator. See `P0_DATA_SCHEMA.md`.

---

## 4. Initial Models

### 4.1 Primary baseline

```text
TF-IDF
+
Logistic Regression
```

**Why Logistic Regression is a good V1 baseline:**

- fast training on laptops
- low resource usage
- fast inference (suitable for near-real-time demo)
- interpretable coefficients (with care for sparse features)
- works well with sparse TF-IDF matrices
- no GPU required
- easy to version and export with scikit-learn style tooling

### 4.2 Optional comparison models

Documented for later ablation / comparison (P8–P9), not required to train in P0:

```text
Naive Bayes
Random Forest
Linear SVM
```

### 4.3 Explicit non-goal for Version 1

Do **not** add deep learning in Version 1 unless later experiments show a measurable need that outweighs complexity, latency, and reproducibility costs.

---

## 5. Input → Features → Model → Output

```text
Input
  - raw authentication log line(s)
  - parsed fields (timestamp, source_id, username, event_type)
  - rolling window state for that source_id
        ↓
Features
  - TF-IDF(clean_log)
  - failed_count_30s / 60s / 5m
  - success_count_5m
  - unique_users_60s
  - attempt_rate
  - time_since_previous_attempt
  - failure_ratio
        ↓
Model
  - Baseline: Logistic Regression (multiclass)
  - Optional comparisons: Naive Bayes, Random Forest, Linear SVM
        ↓
Output
  - prediction ∈ {NORMAL, SUSPICIOUS, BRUTE_FORCE}
  - confidence / class probabilities
  - supporting feature snapshot for dashboard & alerts
```

---

## 6. Evaluation Strategy (future P9)

### 6.1 Metrics to compute

```text
Accuracy
Precision
Recall
F1 Score
Confusion Matrix
Per-class Precision
Per-class Recall
Per-class F1
```

### 6.2 Why Accuracy alone is insufficient

Class imbalance is expected: most events may be `NORMAL`. A model that always predicts `NORMAL` can show high accuracy while missing every attack. Security workflows care about:

- missing real suspicious / brute-force patterns (**false negatives**)
- crying wolf on routine mistakes (**false positives**)

Both must be measured per class.

### 6.3 Project-specific confusion language

Definitions below treat the positive class as the **threat-relevant class under discussion** (usually `BRUTE_FORCE` or `SUSPICIOUS`, depending on the metric slice). Multiclass evaluation will also use one-vs-rest per class.

| Term | Project meaning |
|---|---|
| **True Positive (TP)** | Event/scenario correctly identified as the threat class being measured (e.g., true `BRUTE_FORCE` predicted `BRUTE_FORCE`) |
| **False Positive (FP)** | Benign / lower-severity activity incorrectly escalated (e.g., `NORMAL` predicted `BRUTE_FORCE`) |
| **True Negative (TN)** | Non-target class correctly not assigned the measured positive class |
| **False Negative (FN)** | Threat-relevant activity missed (e.g., true `BRUTE_FORCE` predicted `NORMAL`) |

Special project rule for interpretation:

- Predicting `SUSPICIOUS` for true `BRUTE_FORCE` is better than predicting `NORMAL`, but is still not a perfect detection — report via confusion matrix, not a single accuracy number.

### 6.4 No fabricated scores

P0 records the plan only. Do not invent Precision/Recall/F1 values until trained models and independent test scenarios exist.

---

## 7. Performance Targets (preliminary, not achieved)

Suitable for a lightweight student demonstration on a laptop (including Apple Silicon + Docker).

| Category | Preliminary target | Status |
|---|---|---|
| Log ingestion latency | Poll / read cycle aligned with `monitoring.poll_interval_ms` (default 250 ms) | Not measured yet |
| Feature calculation latency | Typically &lt; 50 ms per event under light load | Not measured yet |
| Model inference latency | Typically &lt; 50 ms per event for LR + TF-IDF under light load | Not measured yet |
| End-to-end scoring latency | Typically &lt; 250 ms parse→infer | Not measured yet |
| Alert delivery latency | Discord webhook attempt shortly after alert decision (network-dependent) | Not measured yet |
| Memory usage | Stay comfortable on a student laptop for demo (no GPU) | Not measured yet |
| CPU usage | Acceptable for local demo; no cloud requirement | Not measured yet |

All values are **targets**, not claims of current performance.

---

## 8. Training / inference separation

| Mode | When | What runs |
|---|---|---|
| Offline training | P8–P10 | Fit vectorizer + model; evaluate; export artifacts |
| Online inference | P11+ | Load artifacts; score new events; no refit by default |

Model artifacts will live under `models/` with version metadata planned in P10.

---

## 9. Dependencies (planned, not installed as a completed stack in P0)

Likely future libraries (subject to `requirements.txt` evolution):

- scikit-learn
- pandas / numpy
- PyYAML for config
- FastAPI or similar for dashboard API (P12)
- Docker / Compose for lab server (P1)

No GPU frameworks are required for the V1 baseline.
