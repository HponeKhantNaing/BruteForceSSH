# P5 Verification

Evaluated: 2026-09-27

| Check | Result | Evidence |
|-------|--------|----------|
| P4 regression | PASS | SHA-256 match vs `data/external/p5/audit/p4_pre_p5_hashes.json` |
| Official-source review | PASS | Loghub GitHub+Zenodo; UNB CIC page; CAM-LDS Zenodo DOI |
| License metadata | PARTIAL | All have research/citation notes; CAM-LDS = LICENSE_REVIEW_REQUIRED |
| Loghub OpenSSH evaluation | PASS | `evaluations/loghub_openssh.json` |
| CIC-IDS2017 evaluation | PASS | `evaluations/cicids2017.json` |
| CAM-LDS evaluation | PASS | `evaluations/cam_lds.json` |
| Compatibility matrix | PASS | `docs/P5_COMPATIBILITY_MATRIX.md` |
| Checksum verification | NOT APPLICABLE | No external dataset files downloaded |
| No forced label mapping | PASS | No public→NORMAL/SUSPICIOUS/BRUTE_FORCE mappings created |
| No P4 mutation | PASS | run_labels / event_annotations / class_distribution hashes unchanged |
| External data separation | PASS | Only under `data/external/p5/` |
| Download policy | PASS | All `download_approved=false`; CLI refuses non-approved downloads |
| Disk-space check | PASS | ≈28 GB free recorded; no large download attempted |
| No P6 canonical dataset | PASS | No `dataset.csv` / train-test builds |
| No P7 features / ML / dashboard | PASS | Not implemented |

## P4 hash verification

```text
data/interim/p4/run_labels.jsonl
  a810db78149c9c5e076a50acc2bb79becbdfc7a0b44532fcc61d6bc130ec1f88

data/interim/p4/event_annotations.jsonl
  46cf21a7658a22fe7cd19e87e0d421778c9cd0b6efe01f965b2393d18a124da7

data/interim/p4/class_distribution.json
  d814679346a7d3ec58f2ef6728c61c622cd413434a52fdc8aa7c8c687bf1790d
```

Status: **MATCH** (pre- and post-P5).
