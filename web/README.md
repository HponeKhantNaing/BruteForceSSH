# BruteWatch — frontend

Vite + React + TypeScript SPA for Lab SSH Login and live Monitor.

## Scripts

```bash
npm install
npm run dev      # http://127.0.0.1:3000 (proxies /api → :8080)
npm run build    # outputs dist/ also served by Flask P12 on :8080
```

## Pages

- `/` — Lab SSH Login (attempt / burst / success)
- `/monitor` — predictions + timeline
- `/alerts` — Discord outbox

Brand assets: `public/brutewatch-mark.png`, `public/favicon.png`.
