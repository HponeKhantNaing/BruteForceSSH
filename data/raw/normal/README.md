# P2 — Normal authentication raw collection

## What this directory contains

Controlled **normal / benign** SSH authentication evidence collected from the
project-owned Ubuntu Docker lab (`ai-security-ubuntu-lab`).

These files are **raw evidence**, not a finished ML dataset.

## Structure

```text
data/raw/normal/
├── README.md
├── index.jsonl
├── P2_<timestamp>_summary.json
└── <SCENARIO_ID>/
    └── <run_id>/
        ├── auth.log
        └── manifest.json
```

## Scenarios (N01–N06)

| ID | Intent |
|---|---|
| `N01_SINGLE_SUCCESS` | Single successful login + clean logout |
| `N02_COMMAND_SESSION` | Login + benign command |
| `N03_SHORT_SESSION` | Short held session |
| `N04_LOW_FREQUENCY_REPEAT` | Low-frequency repeated successes |
| `N05_SESSION_RECONNECT` | Logout then later reconnect |
| `N06_ISOLATED_PASSWORD_MISTAKE` | Exactly one failed password, then recovery success |

## `index.jsonl`

One JSON object per line summarizing each run (paths, checksum, result).
Use it to enumerate the collection without walking directories.

## Why these files are raw

Each `auth.log` is a byte-range slice of the live master log
`data/raw/auth/auth.log` produced by OpenSSH / PAM / rsyslog.

Do **not** manually edit these files.

## Labels

`manifest.json` may include `scenario_intent: "normal"` as collection provenance.

Final per-event ML labels (`NORMAL` / `SUSPICIOUS` / `BRUTE_FORCE`) belong to **P4**, not P2.

## Privacy

Logs may contain lab usernames, Docker bridge source addresses, and timestamps.
Generated run data under this tree is **gitignored** by default.

Anonymization / cleaning is deferred to **P6**.

## Local lab only

```text
P2 data is local controlled lab data.
```

All SSH activity targets `127.0.0.1` / the project container only.
