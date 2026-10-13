# P6 Canonical Dataset (local lab only)

This directory holds the **supervised canonical dataset** built from P4 local ground truth.

## Hard policy

- Public supervised data: **disabled**
- Loghub OpenSSH / CIC-IDS2017 / CAM-LDS: **EXTERNAL_ONLY** (not present here)
- Loghub HDFS: **REJECT**

## Semantic levels

1. **Event** — `canonical_events.jsonl`
2. **Logical authentication attempt** — `canonical_attempts.jsonl`
3. **Contextual run** — `canonical_runs.jsonl` + `canonical_sequences.jsonl`

## P7 handoff

Use runs/events/attempts/sequences + `dataset_manifest.json`.

Do **not** expect TF-IDF, behavioral feature columns, or train/test splits here.
