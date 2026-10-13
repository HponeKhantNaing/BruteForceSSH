# P12 Acceptance Checklist

| Item | Status |
|------|--------|
| P11 PASS verified | PASS |
| P11 prediction schema inspected | PASS |
| P11 prediction stream consumed | PASS |
| P11 runtime event stream consumed or intentionally optional | PASS |
| P11 status consumed | PASS |
| P12 does not parse raw SSH logs | PASS |
| P12 does not load ML model | PASS |
| P12 does not call predict | PASS |
| P12 does not call predict_proba | PASS |
| P12 does not retrain anything | PASS |
| Actual P11 prediction schema validated | PASS |
| Stable event-key dedup implemented | PASS |
| Stable alert-key dedup implemented | PASS |
| SQLite state store implemented | PASS |
| WAL/transaction policy configured | PASS |
| Persistent checkpoint implemented | PASS |
| First-start historical backfill implemented | PASS |
| Historical predictions do not send alerts | PASS |
| New predictions are alert eligible | PASS |
| Restart does not resend processed alerts | PASS |
| NORMAL final does not send Discord | PASS |
| ACTIVE_PREFIX SUSPICIOUS does not send Discord by default | PASS |
| ACTIVE_PREFIX BRUTE_FORCE does not send Discord by default | PASS |
| EPISODE_FINAL SUSPICIOUS sends WARNING | PASS |
| EPISODE_FINAL BRUTE_FORCE sends CRITICAL | PASS |
| No uncalibrated probability threshold used | PASS |
| Alert policy version recorded | PASS |
| 60-second cooldown implemented | PASS |
| Cooldown-suppressed events remain visible | PASS |
| Severity escalation bypasses cooldown | PASS |
| Durable alert outbox implemented | PASS |
| Discord webhook is env-only | PASS |
| Discord URL never logged | PASS |
| Discord URL never sent to browser | PASS |
| Webhook timeout bounded | PASS |
| 429 retry handling implemented | PASS |
| 5xx retry handling implemented | PASS |
| permanent 4xx handling implemented | PASS |
| Discord failure does not stop dashboard | PASS |
| Discord failure does not stop ingestion | PASS |
| Mock Discord integration passes | PASS |
| Real Discord smoke recorded honestly | NOT APPLICABLE |
| No @everyone/@here mentions | PASS |
| Dashboard binds 127.0.0.1 by default | PASS |
| Dashboard works without external CDN | PASS |
| Dashboard shows P11 health | PASS |
| Dashboard shows Discord health | PASS |
| Dashboard shows release ID | PASS |
| Dashboard distinguishes provisional/final | PASS |
| Dashboard distinguishes predictions/alerts | PASS |
| Dashboard displays uncalibrated score warning | PASS |
| Prediction history implemented | PASS |
| Prediction filters implemented | PASS |
| Alert history implemented | PASS |
| Pagination/limits implemented | PASS |
| Dynamic UI content safely escaped | PASS |
| Raw IP not persisted | PASS |
| Raw username not persisted | PASS |
| Password not persisted | PASS |
| Raw log line not included in Discord | PASS |
| Raw identity not shown in dashboard | PASS |
| P11 stale detection works | PASS |
| Malformed prediction handling works | PASS |
| File truncation/replacement handling works | PASS |
| Live normal E2E passes | PASS |
| Live security E2E passes | PASS |
| Synthetic final-BRUTE_FORCE alert E2E passes | PASS |
| Duplicate event test passes | PASS |
| Restart dedup test passes | PASS |
| Historical backfill test passes | PASS |
| Cooldown test passes | PASS |
| Escalation test passes | PASS |
| Privacy test passes | PASS |
| P10 unchanged | PASS |
| P11 unchanged | PASS |
| No model quality metrics recomputed | PASS |
| Performance measured | PASS |
| Documentation matches implementation | PASS |
