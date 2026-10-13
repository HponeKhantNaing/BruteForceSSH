# P0 — Data Strategy

**Phase:** P0 — Project Foundation  
**Status:** Planning only — **no dataset download or collection in P0**

---

## 1. Goal

Build a labeled authentication-activity dataset that supports hybrid ML classification into:

```text
NORMAL | SUSPICIOUS | BRUTE_FORCE
```

Data must come from **authorized** sources only. Controlled attack-like behavior is generated only against the project’s own isolated Ubuntu Docker test server (future P1–P3).

---

## 2. Dataset Sources

### Source A — Locally collected controlled test data (primary)

Future origin: project-owned Ubuntu Docker Test Server authentication / SSH-style logs.

Possible events:

```text
Accepted password
Failed password
Invalid user
Authentication failure
Session opened
Session closed
```

**Role:** Primary realistic log format for this project’s parser and demo.

**Rules:**

- Collect only from the project lab environment
- Preserve raw lines plus parsed fields
- Attach `scenario_id` and `data_source=local_lab`

### Source B — Synthetic / simulated behavior (supporting)

Used to produce controlled test scenarios when natural rarity of attack patterns would otherwise leave the dataset too thin.

**Role:** Fill controlled gaps for `SUSPICIOUS` and `BRUTE_FORCE` scenario design.

**Rules:**

- Synthetic rows must be clearly marked: `data_source=synthetic`
- Synthetic generation settings must be documented (rates, windows, usernames)
- Synthetic data alone is **insufficient** for claiming real-world generalization
- Prefer synthetic data that matches the same schema and approximate log syntax as Source A

### Source C — Public datasets (optional supplementary)

Public log/security datasets may later be evaluated as supplementary data (P5).

**Do NOT download any public dataset during P0.**

Before any future integration, each candidate dataset must be checked for:

| Check | Why |
|---|---|
| License | Redistribution / academic use allowed? |
| Source provenance | Trustworthy origin? |
| Log format | Compatible with our parser assumptions? |
| Labels | Exist? Reliable? Match our class meanings? |
| Compatibility with target problem | Auth/login behavior vs unrelated IDS traffic? |
| Class definition alignment | Does their “attack” mean our `BRUTE_FORCE`? |
| Authentication attack content | Actually contains auth failures / brute patterns? |
| Domain mismatch risk | Cloud syslog ≠ our Docker SSH auth format |

**Do not blindly combine unrelated datasets.**

If a public dataset fails alignment checks, document rejection rather than forcing a merge.

---

## 3. Data directory layout (planned)

```text
data/
├── raw/         # immutable-ish originals (lab exports, marked synthetic dumps)
├── interim/     # parsed / partially cleaned
└── processed/   # feature-ready tables for training/evaluation
```

P0 creates these folders only. No fabricated datasets are placed here.

---

## 4. Collection principles (future)

1. Prefer scenario-based collection sessions over opportunistic scrapes.
2. Every collection run gets a `scenario_id`.
3. Record whether the scenario intent was normal, suspicious, or brute-force **before** labeling individual lines when possible.
4. Keep raw logs immutable; derive cleaned/processed copies.
5. Never store Discord webhooks, passwords, or private keys in data files.

---

## 5. Mixing policy

| Priority | Source | Usage |
|---|---|---|
| 1 | Local lab (A) | Primary training + demo evaluation |
| 2 | Synthetic (B) | Controlled augmentation; always marked |
| 3 | Public (C) | Optional after P5 compatibility review |

When mixing:

- keep `data_source` on every row
- evaluate domain shift (train on A, test on C and vice versa) before claiming benefit
- never silently relabel foreign classes into ours without an explicit mapping document

---

## 6. Privacy / safety

- Lab usernames/passwords are disposable test credentials only
- Do not use real personal credentials
- Mask secrets if they ever appear in logs
- Do not collect data from unauthorized hosts

---

## 7. What P0 does *not* do

- No raw log collection
- No synthetic generator implementation
- No public dataset download
- No labeled CSV fabrication with fake attack rows presented as real results
