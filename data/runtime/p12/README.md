# P12 runtime

SQLite state, service status, and verification artifacts for dashboard/alerts.

```text
p12_state.sqlite3
service_status.json
discord_smoke_report.json
verification_report.json
```

Runtime DB/status are gitignored. P12 consumes P11 structured JSONL only — never raw auth.log.
