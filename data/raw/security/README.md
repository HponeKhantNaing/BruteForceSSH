# P3 — Controlled suspicious / brute-force-like raw collection

## What this directory contains

Bounded authentication-failure scenarios generated **only** against the
project-owned Ubuntu Docker lab on `127.0.0.1`.

These are **raw evidence** files with scenario provenance — not final ML labels.

## Structure

```text
data/raw/security/
├── README.md
├── index.jsonl
├── P3_<batch>_summary.json
├── suspicious/
│   └── <SCENARIO_ID>/<run_id>/{auth.log,manifest.json}
└── brute_force/
    └── <SCENARIO_ID>/<run_id>/{auth.log,manifest.json}
```

## Scenario intent vs ML label

`manifest.json` may contain:

```text
scenario_intent: suspicious | brute_force
```

That is experimental provenance for P4.

Final per-event labels (`NORMAL` / `SUSPICIOUS` / `BRUTE_FORCE`) are **not** assigned here.

## Safety

- Localhost only
- Hard attempt / username / delay / timeout ceilings in code
- No password dictionaries
- No username enumeration / scanning / remote targets

## Privacy

Generated logs are gitignored by default. Do not commit raw runs.
