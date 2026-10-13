# External dataset inventory & training report

**Generated:** 2026-10-08T13:35:08.004953+00:00

## 1. What is on this machine

| Path | Size | Role |
|---|---|---|
| `data/external/corpora/loghub_ssh_full/SSH.log` | 70.0 MB | Loghub OpenSSH full raw logs (~655k lines) |
| `data/external/corpora/loghub_openssh/` | 571.1 KB | Loghub OpenSSH 2k + structured CSV |
| `data/external/corpora/linux_2k/` | 211.4 KB | Loghub-derived Linux_2k sample |
| `data/external/corpora/loghub_linux/` | 2.2 MB | Loghub Linux.tar.gz extract |
| `data/external/corpora/loghub20_openssh/` | 161.1 MB | Loghub-2.0 OpenSSH.zip extract |
| `data/external/downloads/` | 12.4 MB | Compressed downloads (SSH.tar.gz, etc.) |
| `data/external/derived/episodes/` | 5.7 MB | Parsed episodes + features + heuristic labels |
| `data/features/p7/` | 8.1 MB | Lab supervised features (augmented) |
| `data/features/p7_baseline_75/` | 178.6 KB | Frozen original 75 lab runs |
| `artifacts/external/rf-openssh-ext-v1.0.0/` | 4.0 MB | Large RF trained on lab+external |

## 2. Sources (online)

| Source ID | Origin | License / use | Used for train? |
|---|---|---|---|
| `loghub_ssh_full` | [Zenodo Loghub SSH.tar.gz](https://zenodo.org/records/8196385/files/SSH.tar.gz?download=1) | Research/academic with citation (Loghub) | Yes (heuristic labels) |
| `loghub_openssh_2k` | [GitHub logpai/loghub](https://github.com/logpai/loghub) | Research/academic with citation | Yes |
| `loghub_linux` | Zenodo Linux.tar.gz | Research/academic | Corpus kept (not primary SSH auth episodes) |
| `loghub20_openssh` | [Zenodo Loghub-2.0 OpenSSH.zip](https://zenodo.org/records/8275861) | Research/academic | Stored for parsing experiments |
| Kaggle SSH / auth anomalies | Kaggle | Needs `kaggle.json` — **not downloaded** (no API key) | No |
| CIC-IDS2017 / CAM-LDS | P5 evaluated | Network-flow / ATT&CK mismatch — not merged | No (P5 Case B) |

### Episode digest

- Episodes built: **4091**
- Heuristic label counts: `{'SUSPICIOUS': 762, 'NORMAL': 2665, 'BRUTE_FORCE': 664}`

## 3. How data was split for training

| Split | Samples | Method |
|---|---|---|
| Train | **3964** | GroupShuffleSplit by IP/24 (external) + lab scenario groups |
| Validation | **{'split': 'validation', 'n': 1031, 'accuracy': 0.997090203685742, 'balanced_accuracy': 0.9857142857142858, 'macro_precision': 0.9980039920159681, 'macro_recall': 0.9857142857142858, 'macro_f1': 0.9916997289260063, 'weighted_f1': 0.9970627136655442, 'per_class': {'NORMAL': {'precision': 1.0, 'recall': 1.0, 'f1': 1.0, 'support': 463}, 'SUSPICIOUS': {'precision': 0.9940119760479041, 'recall': 1.0, 'f1': 0.996996996996997, 'support': 498}, 'BRUTE_FORCE': {'precision': 1.0, 'recall': 0.9571428571428572, 'f1': 0.9781021897810219, 'support': 70}}, 'confusion_matrix': {'class_order': ['NORMAL', 'SUSPICIOUS', 'BRUTE_FORCE'], 'matrix': [[463, 0, 0], [0, 498, 0], [0, 3, 67]]}, 'origin_counts': {'lab': 600, 'external': 431}, 'report': '              precision    recall  f1-score   support\n\n      NORMAL       1.00      1.00      1.00       463\n  SUSPICIOUS       0.99      1.00      1.00       498\n BRUTE_FORCE       1.00      0.96      0.98        70\n\n    accuracy                           1.00      1031\n   macro avg       1.00      0.99      0.99      1031\nweighted avg       1.00      1.00      1.00      1031\n'}** | From train remainder (group-safe) |
| Test | **{'split': 'test', 'n': 2096, 'accuracy': 1.0, 'balanced_accuracy': 1.0, 'macro_precision': 1.0, 'macro_recall': 1.0, 'macro_f1': 1.0, 'weighted_f1': 1.0, 'per_class': {'NORMAL': {'precision': 1.0, 'recall': 1.0, 'f1': 1.0, 'support': 1652}, 'SUSPICIOUS': {'precision': 1.0, 'recall': 1.0, 'f1': 1.0, 'support': 326}, 'BRUTE_FORCE': {'precision': 1.0, 'recall': 1.0, 'f1': 1.0, 'support': 118}}, 'confusion_matrix': {'class_order': ['NORMAL', 'SUSPICIOUS', 'BRUTE_FORCE'], 'matrix': [[1652, 0, 0], [0, 326, 0], [0, 0, 118]]}, 'origin_counts': {'lab': 800, 'external': 1296}, 'report': '              precision    recall  f1-score   support\n\n      NORMAL       1.00      1.00      1.00      1652\n  SUSPICIOUS       1.00      1.00      1.00       326\n BRUTE_FORCE       1.00      1.00      1.00       118\n\n    accuracy                           1.00      2096\n   macro avg       1.00      1.00      1.00      2096\nweighted avg       1.00      1.00      1.00      2096\n'}** | Held-out groups (20%) |
| Lab gold (weighted ×5) | 3000 | Merged into pool |
| External episodes | 4091 | From Loghub SSH |
| **Total** | **7091** | |

Group leakage control: same `/24` IP (or lab `scenario_id`) never appears in both train and test.

## 4. TEST metrics (combined lab+external RF)

- Model: `RandomForest` n_estimators=800, max_depth=16 → `artifacts/external/rf-openssh-ext-v1.0.0/model.joblib`

| Metric | Value |
|---|---|
| Accuracy | **1.0000** |
| Balanced accuracy | 1.0000 |
| Macro precision | 1.0000 |
| Macro recall | **1.0000** |
| Macro F1 | **1.0000** |
| Weighted F1 | 1.0000 |

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| NORMAL | 1.0000 | 1.0000 | 1.0000 | 1652 |
| SUSPICIOUS | 1.0000 | 1.0000 | 1.0000 | 326 |
| BRUTE_FORCE | 1.0000 | 1.0000 | 1.0000 | 118 |

### Validation snapshot

- Accuracy 0.9971 · Macro F1 0.9917 · Macro recall 0.9857

## 5. Notes

- External labels are **heuristic** (fail-window rules), not human-annotated gold.
- Lab samples keep higher sample weight so controlled-lab ground truth still anchors the model.
- Runtime P11/P12 still points at lab release `rf-behavior-lab-v1.1.0` unless you explicitly switch.
- Cite Loghub when publishing results that used these corpora.

## 6. Important caveat

External `NORMAL/SUSPICIOUS/BRUTE_FORCE` labels were assigned by **the same fail-window heuristics** used to build features. Near-perfect TEST scores partly mean the RF rediscovered those rules — treat external metrics as **rule-recovery / fit check**, not independent human-labeled accuracy. Lab-weighted samples remain the supervised anchor.
