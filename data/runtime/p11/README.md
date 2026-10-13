# P11 runtime outputs

Live monitoring writes prediction events and status here.

```text
predictions.jsonl      structured model outputs (no raw IP/username)
runtime_events.jsonl   lifecycle / error events
status.json            monitor heartbeat
context_policy.json    TRAIN-only idle/max-duration policy
feature_parity_report.json
attempt_parity_report.json
latency_report.json
```

Most runtime files are gitignored. Policy/parity reports may be committed as evidence.
