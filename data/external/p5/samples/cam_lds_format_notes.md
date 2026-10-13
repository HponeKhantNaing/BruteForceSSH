# CAM-LDS — format inspection notes (P5)

**Mode:** Official Zenodo documentation review (metadata-only; no full archive download).  
**Official source:** https://zenodo.org/records/10124280  
**DOI:** 10.5281/zenodo.10124280  
**Access date:** 2026-09-27

## Officially documented facts

- CAM-LDS is a **Linux** cyber-attack management / system-log dataset published on Zenodo.
- It includes **multi-source host logs** and **attack scenario documentation**.
- Labels follow **MITRE ATT&CK technique / scenario** semantics rather than a three-class auth ontology.
- Brute-force-related activity (e.g., hydra-style tooling) may appear as **techniques**, not as our contextual class `BRUTE_FORCE`.

## Project interpretation

- Host-log relevance is **higher than CIC-IDS2017**, but still **not schema-compatible** with P4 run labels.
- Mapping MITRE technique X → BRUTE_FORCE without documented semantic equivalence is **invalid**.
- Our intermediate `SUSPICIOUS` class is **not** provided.

## License note

Exact Zenodo license text must be re-checked before any redistribution → `LICENSE_REVIEW_REQUIRED`.

## Decision implication

`EXTERNAL_LABELED_EVALUATION` — external labeled reference only.
