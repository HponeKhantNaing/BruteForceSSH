# AI-Based Real-Time Server Log Threat Detection and Alert System

## Current Phase

```text
P12 — Dashboard + Discord Alert Integration
```

## Progress

```text
P0 ✅
P1 ✅
P2 ✅
P3 ✅
P4 ✅
P5 ✅
P6 ✅
P7 ✅
P8 ✅
P9 ✅
P10 ✅
P11 ✅
P12 ✅

V1 SYSTEM COMPLETE — CONTROLLED-LAB V1
```

## Current Status

**P12 complete:** BruteWatch — P11 predictions → SQLite → TypeScript Lab Login + Monitor SPA + durable Discord outbox (`final_non_normal`).

| Item | Value |
|------|-------|
| Product | BruteWatch |
| Lab Login | http://127.0.0.1:3000/ (Vite) or :8080 |
| Monitor | http://127.0.0.1:3000/monitor |
| Alert policy | `p12-alert-v1` |
| Discord default | finals SUSPICIOUS/BRUTE_FORCE only |
| Maturity | CONTROLLED-LAB V1 (not production-proven) |

---

## Quick Commands

```bash
# Frontend (once / after UI changes)
cd web && npm install && npm run build && cd ..

# P11
python3 scripts/p11_realtime_monitor.py --monitor --duration-seconds 0

# P12
python3 scripts/p12_dashboard_alerts.py --init
python3 scripts/p12_dashboard_alerts.py --run
python3 scripts/p12_dashboard_alerts.py --report
```

Self-test without terminal collectors: open Lab Login, type lab username/password, use Attempt / Fail burst / Success — see [`docs/SYSTEM_RUNBOOK.md`](docs/SYSTEM_RUNBOOK.md).

---

## Docs

- [`docs/P12_DASHBOARD_DISCORD.md`](docs/P12_DASHBOARD_DISCORD.md)
- [`docs/P12_ALERT_POLICY.md`](docs/P12_ALERT_POLICY.md)
- [`docs/SYSTEM_RUNBOOK.md`](docs/SYSTEM_RUNBOOK.md)
- [`docs/V1_SYSTEM_ARCHITECTURE.md`](docs/V1_SYSTEM_ARCHITECTURE.md)
- [`docs/P12_ACCEPTANCE_CHECKLIST.md`](docs/P12_ACCEPTANCE_CHECKLIST.md)
