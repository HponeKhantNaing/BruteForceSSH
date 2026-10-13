# External public-data evaluation (P5)

This directory holds **external** dataset evaluation artifacts only.

## Why separated?

Local controlled lab evidence lives under:

- `data/raw/normal/`
- `data/raw/security/`
- `data/interim/p4/`

Public/third-party data must **never** be mixed into those roots.

## Contents

| Path | Role |
|------|------|
| `registry.json` | Authoritative candidate registry + final P5 decisions |
| `evaluations/` | Per-dataset evaluation JSON |
| `samples/` | Format notes / inspection notes (not cleaned datasets) |
| `downloads/` | Optional retained downloads (**gitignored**) |
| `external_files.jsonl` | Provenance for downloaded files (created when files exist) |
| `integration_candidates.jsonl` | Present only if DIRECT_INTEGRATION_CANDIDATE exists |
| `source_snapshot.json` | Official URL / version / access-date snapshot |
| `audit/` | P4 hash regression snapshots |

## Evaluation status (P5)

Public supervised integration: **none approved**.

| Dataset | Decision |
|---------|----------|
| Loghub OpenSSH | EXTERNAL_UNLABELED_CORPUS |
| CIC-IDS2017 | EXTERNAL_LABELED_EVALUATION |
| CAM-LDS | EXTERNAL_LABELED_EVALUATION |
| Loghub HDFS | REJECT |

## License caveat

Public download ≠ unrestricted redistribution. See `docs/P5_DATASET_SOURCES.md`.

## P6 boundary

P6 may **consider** external sources only as marked in the registry (`p6_disposition`).  
P6 must **not** invent labels or merge network flows into the host-log supervised table without a new justified design.
