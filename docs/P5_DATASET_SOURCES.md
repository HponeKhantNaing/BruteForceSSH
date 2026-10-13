# P5 Dataset Sources

Access date for all entries unless noted: **2026-09-27**.

This document separates **officially documented facts** from **project interpretation**.

---

## Candidate A — Loghub OpenSSH

| Field | Value |
|-------|-------|
| Dataset name | Loghub OpenSSH |
| Official source | https://github.com/logpai/loghub |
| Alternate / DOI | https://doi.org/10.5281/zenodo.1144100 (Zenodo 1144100) |
| Publisher | LogPAI / Loghub project |
| Associated paper | He et al., *Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics* (arXiv:2008.06448) |
| Access date | 2026-09-27 |

### License / usage terms (documented)

- Loghub states datasets are **free for research**.
- **Citation** of the Loghub paper / repository is required.
- Redistribution of the full corpus is **not assumed unrestricted**.

### Officially documented facts

- Includes an **OpenSSH** host system-log corpus among other services.
- Format is **raw OpenSSH / sshd syslog-style** lines.
- OpenSSH subset size is on the order of **tens of MB** (commonly cited ≈70 MB).
- Intended use: AI-driven log analytics research.
- **No** project-compatible NORMAL / SUSPICIOUS / BRUTE_FORCE ground-truth labels are published for this subset.

### Project interpretation

- High domain similarity to V1 (host OpenSSH auth logs).
- Treat as unlabeled external corpus only; do not invent supervised labels.

---

## Candidate B — CIC-IDS2017

| Field | Value |
|-------|-------|
| Dataset name | CIC-IDS2017 |
| Official source | https://www.unb.ca/cic/datasets/ids-2017.html |
| Publisher | Canadian Institute for Cybersecurity (CIC), University of New Brunswick |
| Associated paper | Sharafaldin, Lashkari, Ghorbani — *Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization* (ICISSP 2018) |
| Access date | 2026-09-27 |

### License / usage terms (documented)

- Distributed by UNB CIC for **academic / research** use under CIC dataset terms.
- **Citation** of the CIC-IDS2017 paper / CIC page is required.
- Full-dataset **redistribution** is not assumed permitted.

### Officially documented facts

- Provides **PCAP** and **CICFlowMeter-derived CSV** labeled traffic.
- Includes **SSH-Patator** brute-force activity among attack categories.
- Labels apply to **network flows / traffic**, not host `auth.log` lines.
- Collection year **2017**; paper **2018**.
- Corpus size is **multi-GB**.

### Project interpretation

- SSH brute-force coverage exists in the **network domain**.
- Not schema-compatible with P4 host-log contextual samples.
- Keep as `EXTERNAL_LABELED_EVALUATION`.

---

## Candidate C — CAM-LDS

| Field | Value |
|-------|-------|
| Dataset name | CAM-LDS (Cyber Attack Management - Linux Dataset) |
| Official source | https://zenodo.org/records/10124280 |
| DOI | 10.5281/zenodo.10124280 |
| Publisher | AIT / CAM-LDS authors via Zenodo |
| Access date | 2026-09-27 |

### License / usage terms (documented)

- Zenodo record includes a license statement; exact redistribution terms must be confirmed before sharing files → **LICENSE_REVIEW_REQUIRED**.
- Academic research use is the intended framing; **citation** required.

### Officially documented facts

- Linux **multi-source system logs** with attack scenario documentation.
- Labels follow **MITRE ATT&CK technique / scenario** semantics.
- May include brute-force-related techniques (e.g., hydra-style) as **ATT&CK techniques**, not as our three contextual classes.
- Full archives are **large** (multi-GB class).

### Project interpretation

- Host-log relevance is higher than CIC-IDS2017, but label ontology is incompatible for direct supervised merge.
- No automatic MITRE → BRUTE_FORCE / SUSPICIOUS mapping.

---

## Rejected domain example — Loghub HDFS

| Field | Value |
|-------|-------|
| Dataset name | Loghub HDFS |
| Official source | https://github.com/logpai/loghub |
| Access date | 2026-09-27 |

### Officially documented facts

- Labeled **normal / anomaly** HDFS logs for distributed filesystem analytics.

### Project interpretation

- Wrong domain. Labeled ≠ relevant. **REJECT**.

---

## Additional search notes

Search themes reviewed (authoritative pages preferred):

- labeled SSH authentication log datasets
- Linux authentication security log datasets
- SSH brute-force host-log datasets

**Finding:** No stronger host-log dataset with trustworthy NORMAL / SUSPICIOUS / BRUTE_FORCE-compatible labeling was identified that outranks the three primary candidates for V1 supervised integration.
