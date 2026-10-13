# P11 Acceptance Checklist

| Item | Status |
|------|--------|
| P10 PASS verified | PASS |
| P10 bundle checksums verified | PASS |
| Correct release loaded | PASS |
| Correct model loaded | PASS |
| Model class order verified | PASS |
| 22-feature contract loaded | PASS |
| No TF-IDF dependency | PASS |
| No StandardScaler dependency | PASS |
| No model refitting | PASS |
| No online learning | PASS |
| Live log source verified | PASS |
| File tailer implemented | PASS |
| Log truncation handled | PASS |
| Log rotation/replacement handled | PASS |
| P6 parser semantics reused | PASS |
| Stateful attempt reconstruction implemented | PASS |
| PAM/AUTH failure double-count prevented | PASS |
| Session events do not create extra attempts | PASS |
| P6 historical attempt parity passes | PASS |
| P7 feature definitions reused | PASS |
| 30s window semantics match | PASS |
| 60s window semantics match | PASS |
| 5m window semantics match | PASS |
| Inclusive [t-W,t] semantics preserved | PASS |
| 75 historical feature parity checks pass | PASS |
| Per-source episode state implemented | PASS |
| Source contexts isolated | PASS |
| Runtime usernames pseudonymized | PASS |
| Runtime sources pseudonymized in persisted output | PASS |
| Context timeout derived without TEST tuning | PASS |
| Max episode duration bounded | PASS |
| Idle timeout close implemented | PASS |
| Active prefix prediction implemented | PASS |
| Active prefix marked provisional | PASS |
| Episode final prediction implemented | PASS |
| Idle timeout not added to model duration | PASS |
| Input contract validated before inference | PASS |
| Exact feature order used | PASS |
| model.predict works | PASS |
| predict_proba mapping uses model.classes_ | PASS |
| Probabilities marked uncalibrated | PASS |
| Prediction JSONL store implemented | PASS |
| No raw IP persisted | PASS |
| No raw username persisted | PASS |
| No password persisted | PASS |
| No alert threshold added | PASS |
| No Discord added | PASS |
| No dashboard added | PASS |
| No firewall/blocking added | PASS |
| Live normal scenario passes end-to-end | PASS |
| Live security scenario passes end-to-end | PASS |
| One failed login produces one logical failure | PASS |
| Source/release inference parity passes | PASS |
| Runtime memory bounded | PASS |
| Restart behavior documented | PASS |
| Latency measured | PASS |
| Documentation matches runtime behavior | PASS |
| P12 handoff generated | PASS |
