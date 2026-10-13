# P6 Canonical Dataset

## Objective

Convert immutable local auth logs + P4 ground truth into a clean, traceable canonical dataset for P7 — without features, TF-IDF, ML, or public supervised merges.

## Input Sources

| Source | Path |
|--------|------|
| Run labels | `data/interim/p4/run_labels.jsonl` |
| Event annotations | `data/interim/p4/event_annotations.jsonl` |
| Raw evidence | `data/raw/normal/`, `data/raw/security/` |
| P5 registry (policy only) | `data/external/p5/registry.json` |

## P5 Public Data Decision

| Dataset | Disposition |
|---------|-------------|
| Loghub OpenSSH | EXTERNAL_ONLY |
| CIC-IDS2017 | EXTERNAL_ONLY |
| CAM-LDS | EXTERNAL_ONLY |
| Loghub HDFS | REJECT |

`external_supervised_data.enabled = false` in `config/p6_preprocessing.yaml`.

## Why Local P4 Is Primary

P5 found no `DIRECT_INTEGRATION_CANDIDATE`. Public corpora lack compatible NORMAL/SUSPICIOUS/BRUTE_FORCE host-log labels and/or use incompatible representations.

## Three Semantic Levels

1. **Log event** — one auth log line (`canonical_events.jsonl`)
2. **Logical authentication attempt** — one login try (`canonical_attempts.jsonl`)
3. **Contextual run** — one supervised sample (`canonical_runs.jsonl` / sequences)

## Event vs Attempt vs Run

- Target labels (`NORMAL` / `SUSPICIOUS` / `BRUTE_FORCE`) stay **run-level** from P4.
- Attempt outcomes are only `SUCCESS` / `FAILURE` / `UNKNOWN`.
- Events preserve PAM + Failed password as **two events**, one attempt.

## Failure Double-Counting Problem

P4 observed AUTH_FAILURE=345 and PAM_AUTH_FAILURE=345. Summing them would invent 690 failures. P6 pairs same-`sshd` PID PAM+Failed password → **345 logical FAILURE attempts**.

## Parsing

Observed ISO OpenSSH/PAM lines via `src/preprocessing/auth_parser.py`. No fabricated fields.

## Normalization

Lowercase messages; replace timestamp/IP/port/PID/hostname/username placeholders; keep semantic words (`failed password`, `accepted password`, `authentication failure`, `session opened/closed`).

## Anonymization

Deterministic `USR_###` / `SRC_###` from sorted unique values. No reversible mapping persisted.

## Attempt Reconstruction

Method: `sshd_pid_time_event_correlation`. Validated against manifest / event_summary counts.

## Canonical Schemas

Under `data/processed/p6/schemas/`.

## Noise Policy

`OTHER_AUTH` / `UNCLASSIFIED` marked `is_infrastructure_noise`; not silently deleted.

## Leakage Prevention

Scenario IDs, target labels, P2/P3, class-bearing paths, raw IPs/usernames excluded from model-eligible text.

## Class Preservation

75 runs → NORMAL 30 / SUSPICIOUS 20 / BRUTE_FORCE 25 (no balancing).

## Quality Gates

Source hashes, P5 policy, join integrity, leakage scan, manifest attempt matches, determinism.

## Limitations

Single Docker lab; limited identity diversity; OpenSSH-specific pairing; INVALID_USER=0 in current data.

## P7 Handoff

Consume:

- `canonical_runs.jsonl`
- `canonical_events.jsonl`
- `canonical_attempts.jsonl`
- `canonical_sequences.jsonl`
- `dataset_manifest.json`

P7 derives TF-IDF + behavioral features. P6 does not.
