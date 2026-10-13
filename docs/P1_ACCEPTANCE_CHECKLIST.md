# P1 — Acceptance Checklist

P1 is complete only if every item below is satisfied with real verification evidence in `P1_VERIFICATION.md`.

```text
[x] Ubuntu Docker image builds
[x] Container starts
[x] Container becomes healthy
[x] SSH daemon config is valid
[x] Root SSH login disabled
[x] Empty password login disabled
[x] Test user exists
[x] Valid SSH login succeeds
[x] Failed SSH login is rejected
[x] Successful login creates a real auth log
[x] Failed login creates a real auth log
[x] Auth log accessible from host project
[x] P2 log path documented
[x] Logs can be preserved/reset predictably
[x] SSH host binding is local-only
[x] No real secrets committed
[x] .env ignored (listed in .gitignore)
[x] No ML implementation added
[x] No dashboard added
[x] No Discord integration added
[x] No external system targeted
[x] Restart test passes
[x] P1 verification document contains real results
```

## Explicit non-claims

- P2 log collection automation is **not** implemented
- No attack/brute-force generator scripts were added
- No ML training or inference was added
- No dashboard UI was added
- No Discord webhook was configured or tested
