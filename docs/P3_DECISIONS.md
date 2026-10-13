# P3 — Decision Log

**Phase:** P3 — Controlled Suspicious / Brute-Force Scenario Collection

---

## P0–P2 preservation

- Failed password ≠ automatic brute force
- Lab remains localhost Docker only
- P2 normal collection remains separate under `data/raw/normal/`
- No final ML labels / features / training / dashboard / Discord in P3

---

## P3 decisions

| Decision | Choice | Reason | Alternatives | Revisit When |
|---|---|---|---|---|
| Suspicious scenarios | S01–S04 | Cover rate, recovery, multi-user, small cluster | Fewer scenarios | P4 needs more ambiguity cases |
| Brute-force scenarios | B01–B05 | Burst, sustained, multi-user, recovery, dual burst | Drop B05 | Runtime too long for demos |
| Hard attempt cap | 30 | Bound dataset generation | Higher/lower | Institutional policy |
| Hard username cap | 6 | Prevent dictionary-style sprays | Higher | Never for generic tooling |
| Minimum delay | 0.25s | Avoid tight CPU loops; not attack optimization | 0 delay | Never for P3 |
| Scenario timeout | 120s | Fail runaway runs | Longer | Sustained windows need more |
| Local-only policy | Hard fail non-localhost | Safety boundary | Soft warn | Never |
| Sequential execution | Single-threaded Paramiko | No parallel attack engine | Thread pools | Never for P3 |
| Output layout | `data/raw/security/{suspicious,brute_force}/` | Separate from P2 | Shared tree | Path rename only |
| Manifest extensions | Attempt/user/duration ground truth | Help P4 without labeling | Logs only | Schema evolution |
| Batch target | 5 runs × enabled scenarios | Balanced small baseline | Larger sets | More data needed |
| Wrong-password strategy | 3 internal constants | No wordlist files | External list | Never add rockyou |
| No password wordlists | Enforced by design | Not an attack tool | Dict support | Never |
| No generic target option | No `--host`/`--target` | Prevent misuse | Configurable host | Never for default CLI |
| Extra lab users | labuser1–3 via docker exec | Explicit multi-user scenarios | Invalid-user only | Image bake in later |
| SSH client | Reuse Paramiko from P2 | Predictable single attempts | sshpass/expect | Auth retry quirks |

---

## Threshold disclaimer

P3 scenario intensities are **experimental**. They do **not** prove that “8 failures = always BRUTE_FORCE”. Final thresholds/models are evaluated in P9.
