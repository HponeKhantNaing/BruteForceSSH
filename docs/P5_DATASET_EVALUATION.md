# P5 Dataset Evaluation

## Objective

Evaluate whether any public dataset can safely support this project's V1 supervised path for **Linux / OpenSSH authentication** threat detection — without forcing a merge, inventing labels, or weakening quality.

## Current Project Domain

| Item | Value |
|------|-------|
| Detection domain | Linux / OpenSSH authentication activity |
| Contextual targets | NORMAL, SUSPICIOUS, BRUTE_FORCE |
| Raw source type | Host-side authentication logs |
| Primary supervised source | `data/interim/p4/run_labels.jsonl` (75 runs: 30/20/25) |
| Public data | **Optional** |

## Evaluation Method

1. Inspect P0–P4 state and freeze P4 hashes.
2. Prefer official sources (university/Zenodo/DOI/GitHub project pages).
3. Score candidates with `config/p5_dataset_evaluation.yaml` (required gates override raw scores).
4. Classify representation (host log vs network flow vs other).
5. Review licenses, labels, schema, sequence context, leakage risks.
6. Staged download policy: **metadata-first**; no auto-download; large downloads refused without approval.
7. Assign exactly one decision per dataset; set P6 disposition.

## Candidates

| ID | Name | Official source |
|----|------|-----------------|
| loghub_openssh | Loghub OpenSSH | https://github.com/logpai/loghub |
| cicids2017 | CIC-IDS2017 | https://www.unb.ca/cic/datasets/ids-2017.html |
| cam_lds | CAM-LDS | https://zenodo.org/records/10124280 |
| loghub_hdfs | Loghub HDFS (reject example) | https://github.com/logpai/loghub |

## Dataset A Findings — Loghub OpenSSH

- **Domain:** host OpenSSH/sshd logs — strong format match.
- **Labels:** none compatible → `UNLABELED`.
- **Use:** parser robustness / format diversity later.
- **Decision:** `EXTERNAL_UNLABELED_CORPUS`.
- **Supervised integration:** NO.

## Dataset B Findings — CIC-IDS2017

- **Domain:** PCAP + flow CSV (CICFlowMeter).
- **SSH:** SSH-Patator labeled in network traffic.
- **Host auth logs:** no.
- **Mismatch:** `HOST_LOG_VS_NETWORK_FLOW = HIGH`.
- **Decision:** `EXTERNAL_LABELED_EVALUATION`.
- **Direct merge:** NO.

## Dataset C Findings — CAM-LDS

- **Domain:** Linux multi-source host logs.
- **Labels:** MITRE ATT&CK techniques / scenarios — not our three classes.
- **Mapping:** incompatible for automatic merge; no MITRE→BRUTE_FORCE shortcut.
- **License:** `LICENSE_REVIEW_REQUIRED` before redistribution.
- **Decision:** `EXTERNAL_LABELED_EVALUATION`.

## Additional Candidates

No additional candidate provided stronger compatibility than the reviewed primary candidates for V1 supervised host-log integration. Loghub HDFS was recorded explicitly as a labeled-but-irrelevant rejection example.

## License Review

| Dataset | Status | Notes |
|---------|--------|-------|
| Loghub OpenSSH | RESEARCH_USE_WITH_CITATION | Cite Loghub; redistribution not assumed free |
| CIC-IDS2017 | ACADEMIC_RESEARCH_VIA_CIC_TERMS | Cite CIC; follow UNB CIC terms |
| CAM-LDS | LICENSE_REVIEW_REQUIRED | Confirm Zenodo license before redistribute |
| Loghub HDFS | RESEARCH_USE_WITH_CITATION | Rejected on domain |

## Compatibility Matrix

See [`P5_COMPATIBILITY_MATRIX.md`](P5_COMPATIBILITY_MATRIX.md).

## Domain Mismatch Analysis

| Category | Loghub OpenSSH | CIC-IDS2017 | CAM-LDS |
|----------|----------------|-------------|---------|
| HOST_LOG_VS_NETWORK_FLOW | LOW | HIGH | LOW |
| LABEL_SEMANTICS | HIGH | HIGH | HIGH |
| TIMESTAMP_CONTEXT | LOW | MEDIUM | MEDIUM |
| SCHEMA | MEDIUM | HIGH | MEDIUM |
| OPERATING_SYSTEM | LOW | MEDIUM | LOW |
| AUTH_PROTOCOL | LOW | MEDIUM | MEDIUM |
| COLLECTION_ENVIRONMENT | MEDIUM | HIGH | MEDIUM |
| CLASS_COVERAGE | HIGH | HIGH | HIGH |

## Label Compatibility

| Dataset | Level | Notes |
|---------|-------|-------|
| Loghub OpenSSH | UNLABELED | No invented labels |
| CIC-IDS2017 | INCOMPATIBLE | Flow attack categories ≠ contextual auth classes |
| CAM-LDS | INCOMPATIBLE | MITRE techniques ≠ NORMAL/SUSPICIOUS/BRUTE_FORCE |
| Loghub HDFS | INCOMPATIBLE | anomaly ≠ SUSPICIOUS |

**No public label was mapped to NORMAL, SUSPICIOUS, or BRUTE_FORCE.**

## Leakage Risks

- **Fixed source IP / attacker identity:** HIGH for CIC lab captures; MEDIUM elsewhere — do not learn IP=malicious.
- **Time-window shortcut:** HIGH for CIC scheduled attack days; MEDIUM for CAM scenarios.
- **Scenario / label leakage:** HIGH for technique-scripted datasets if used without care.
- **Duplicates:** literature notes CIC flow duplication issues — document only (no cleaning in P5).

## Storage / Download Practicality

| Check | Result |
|-------|--------|
| Available disk (eval host) | ≈28 GB free |
| Full CIC / CAM download | Multi-GB — **not justified** given domain/label decisions |
| Loghub OpenSSH | ≈70 MB class — still not downloaded; unlabeled status already decisive |
| Policy | `download_approved=false` for all candidates |

## Decisions

| Dataset | Decision | P6 disposition |
|---------|----------|----------------|
| Loghub OpenSSH | EXTERNAL_UNLABELED_CORPUS | EXTERNAL_ONLY |
| CIC-IDS2017 | EXTERNAL_LABELED_EVALUATION | EXTERNAL_ONLY |
| CAM-LDS | EXTERNAL_LABELED_EVALUATION | EXTERNAL_ONLY |
| Loghub HDFS | REJECT | REJECT |

## Integration Plan

**Case B:** No public dataset approved for direct supervised integration.

Local P4 ground truth remains the **only** primary supervised source for P6 canonical build.

External corpora may be revisited later for:

- parser robustness (Loghub OpenSSH)
- separate network-domain experiments (CIC)
- careful MITRE-subset research (CAM-LDS) with new review

## Rejections

- Loghub HDFS: wrong domain.
- All candidates for `DIRECT_INTEGRATION_CANDIDATE`: failed label and/or representation gates.

## P6 Handoff

| Artifact | Path |
|----------|------|
| Local run labels | `data/interim/p4/run_labels.jsonl` |
| Local event annotations | `data/interim/p4/event_annotations.jsonl` |
| External registry | `data/external/p5/registry.json` |
| Evaluations | `data/external/p5/evaluations/` |
| External file manifest | NOT APPLICABLE (no downloads) |
| Integration candidates | NONE |

P6 must **not guess**: only EXTERNAL_ONLY / REJECT dispositions exist; no INCLUDE_CANDIDATE.
