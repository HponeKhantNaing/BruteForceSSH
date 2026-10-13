# P10 Decisions

| Decision | Choice | Reason | Alternatives | Revisit When |
|---|---|---|---|---|
| Package exact P9-evaluated artifact | Direct `shutil.copy2` of P8 RF joblib | Preserves byte identity and evaluation provenance | Re-serialize / round-trip dump | Never for same release ID |
| No retraining | Fit calls forbidden in export path | P10 is packaging, not training | Retrain inside export | New MAJOR model version |
| Lab release channel | `lab` | Controlled-lab maturity only | `production` | After broader validation |
| Semantic versioning | `rf-behavior-lab-v1.0.0` / SemVer | Immutable release IDs | Date-only tags | Each packaging change |
| RF raw behavioral representation | `behavior_raw` | Matches P9 selection; RF trained on unscaled behavior | Scaled behavior / hybrid / text | Model reselection |
| No TF-IDF dependency | `tfidf_required: false` | Selected model does not use text features | Bundle vectorizer anyway | If text model selected later |
| No scaler dependency | `scaler_required: false` | RF used raw features | Bundle StandardScaler | If scaled model selected |
| Strict 22-feature contract | Named required fields; reject extras | Prevent schema drift | Allow extras / sparse inputs | Contract MINOR/MAJOR bump |
| Model class order stored explicitly | Record `model.classes_` | Sklearn order ≠ presentation order | Assume alphabetical | Retrain changes classes_ |
| Uncalibrated probability labeling | `probability_type: uncalibrated` | No calibration in P8/P9 | Call them confidence | After calibration study |
| Immutable release versions | Refuse overwrite of existing release dir | Auditability | Overwrite in place | Never |
| Checksum everything important | `CHECKSUMS.sha256` (exclude self) | Tamper detection | Manifest-only hashes | Packaging layout change |
| Offline smoke test only | Synthetic valid vector | Packaging regression ≠ accuracy | Re-run P9 TEST | Never in P10 |
