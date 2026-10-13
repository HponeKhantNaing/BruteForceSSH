# P2 — Decision Log

**Phase:** P2 — Normal Log Collection  
**Rule:** Do not silently change P0/P1 decisions.

---

## P0/P1 preservation

- Detection scope remains authentication / login monitoring
- Classes remain `NORMAL` / `SUSPICIOUS` / `BRUTE_FORCE` (final labeling still P4)
- Failed password ≠ automatic brute force (N06 preserves this)
- Lab remains project-owned Docker Ubuntu on localhost
- No ML, dashboard, or Discord in P2

---

## P2 decisions

| Decision | Choice | Reason | Alternatives | Revisit When |
|---|---|---|---|---|
| Normal scenario set | N01–N06 as catalogued | Covers success, commands, short hold, low-frequency repeat, reconnect, isolated mistake | Fewer scenarios; synthetic-only | P3 needs additional benign baselines |
| SSH automation method | Paramiko (password only) | Reliable automation without `sshpass`; env credentials | Expect+OpenSSH; fabric | Paramiko auth quirks on future hosts |
| Master log boundary method | Byte offset + flush poll | Deterministic slice of live `data/raw/auth/auth.log` | Full-file copy; timestamp windows | Clock skew / rotation appears |
| Raw directory structure | `data/raw/normal/<scenario>/<run_id>/` | Clear scenario isolation; non-overwrite | Flat dump; single combined file | Scale issues |
| Manifest format | JSON provenance (`scenario_intent`, not final label) | Answers where/when/how without P4 labeling | CSV rows with labels | Schema evolution in P4/P6 |
| Index format | `index.jsonl` one object per run | Fast enumeration | SQLite; directory walk only | Very large collections |
| Checksum algorithm | SHA-256 | Standard integrity proof | SHA-1; MD5 | Policy change |
| Batch strategy | `collection_batch_id` + summary JSON | Tracks a complete collection invocation | Per-run only | Multi-host batches |
| Isolated failed-login policy | Exactly 1 intentional failure in N06 | Encodes benign mistake without P3 burst | Zero failures only | Evidence shows Paramiko multi-try |
| Collection pacing | `min_gap_seconds=3`; scenarios use 10s | Prevents attack-like reconnect loops | Faster gaps | Demo time constraints |
| Credential strategy | `.env` / `LAB_SSH_*` only | No secrets in manifests/git | Prompt each run | Secret manager later |
| Localhost guard | Hard fail unless `127.0.0.1`/`localhost` | Enforce lab-only safety | Soft warning | Never for default P2 |
| Dependency adds | `paramiko`, `python-dotenv` (+ existing PyYAML) | Required for P2 runner | Shell-only SSH | Prefer fewer deps later |
| Gitignore policy | Ignore `data/raw/normal/**` except README | Privacy; raw logs stay local | Commit samples | Sanitized samples in P6 |

---

## Notes

Smoke runs (`P2_SMOKE`) and baseline (`P2_BASELINE_20260927T070000Z`) share the same index file; run IDs remain unique.
