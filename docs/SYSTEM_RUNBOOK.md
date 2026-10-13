# System Runbook (CONTROLLED-LAB V1)

For local controlled-lab use only. Dashboard binds `127.0.0.1` by default.

## Primary path: Lab Login UI (no terminal collectors)

### 1. Start Ubuntu lab

```bash
docker compose up -d
docker compose ps
```

### 2. Start P11 monitor

```bash
set -a && source .env && set +a
python3 scripts/p11_realtime_monitor.py --monitor --duration-seconds 0
```

### 3. Build TypeScript UI (once, or after UI changes)

```bash
cd web && npm install && npm run build && cd ..
```

### 4. Start P12 (API + SPA)

```bash
set -a && source .env && set +a
python3 scripts/p12_dashboard_alerts.py --validate
python3 scripts/p12_dashboard_alerts.py --init   # first time only
python3 scripts/p12_dashboard_alerts.py --run
```

### 5. Open Lab Login

```text
http://127.0.0.1:8080/
```

| Control | What to type / click |
|---------|----------------------|
| Username | Lab user, e.g. `testuser` |
| Password | Correct lab password **or** a wrong password |
| **Attempt once** | One real SSH auth against Docker `:2222` |
| **Fail burst (N)** | N wrong-password attempts (3–10) |
| **Success session** | Accepted login then exit (needs correct password) |

Then open **Monitor** → http://127.0.0.1:8080/monitor  
Wait ~30s after activity for `EPISODE_FINAL`. SUSPICIOUS / BRUTE_FORCE finals send Discord when enabled.

### Dev UI on localhost:3000 (recommended)

With P12 API running on `:8080`:

```bash
cd web && npm run dev
```

Open http://127.0.0.1:3000/ — Vite proxies `/api` → `:8080`.

## Optional Discord

```bash
export P12_DISCORD_ENABLED=true
export DISCORD_WEBHOOK_URL='https://discord.com/api/webhooks/...'
python3 scripts/p12_dashboard_alerts.py --discord-smoke-test
```

## Optional CLI collectors (legacy)

```bash
python3 scripts/p2_collect_normal.py --scenario N01_SINGLE_SUCCESS --repetitions 1
python3 scripts/p3_collect_security.py --scenario B01_SHORT_FAILURE_BURST --repetitions 1 --batch-id DEMO
```

Prefer Lab Login UI for demos.

## Stop

Ctrl+C P11 and P12. `docker compose stop` if desired.

## Status

```bash
python3 scripts/p11_realtime_monitor.py --report
python3 scripts/p12_dashboard_alerts.py --report
curl -s http://127.0.0.1:8080/api/lab/status
```

## Troubleshoot

| Symptom | Check |
|---------|--------|
| Blank / build message on `/` | `cd web && npm run build` |
| Lab attempt 502 | Docker healthy? `docker compose ps` |
| Rate limited | Wait 60s (max 20 attempts/min) |
| P11 STALE | Normal when idle; is monitor running? |
| No Discord | Env vars + FINAL non-NORMAL only |
