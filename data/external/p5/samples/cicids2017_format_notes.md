# CIC-IDS2017 — format inspection notes (P5)

**Mode:** Official documentation review (metadata-only; no multi-GB download).  
**Official source:** https://www.unb.ca/cic/datasets/ids-2017.html  
**Publisher:** Canadian Institute for Cybersecurity (CIC), University of New Brunswick  
**Access date:** 2026-09-27

## Officially documented facts

- CIC-IDS2017 provides **PCAP** captures and **machine-learning CSV** derived via CICFlowMeter.
- Traffic includes **benign** and multiple **attack** categories.
- Documentation includes **SSH-Patator** brute-force activity (commonly associated with the Tuesday capture day).
- Labels apply to **network flows / traffic**, not to host-side `auth.log` lines.
- Academic use requires following **CIC dataset terms** and **citation**.

## Project interpretation

- SSH brute-force **behavior exists**, but as **network-domain evidence**.
- Benign flows are **not** equivalent to NORMAL SSH authentication sessions.
- Direct concatenation of CIC flow rows with P4 run-level host-log features is **forbidden** for V1.

## Illustrative CSV concept (schema family; not a retained CIC file)

```text
Flow features: Duration, Protocol, Src IP, Dst IP, ... , Label
Label examples (conceptual): BENIGN, SSH-Patator, ...
```

No `username`, `sshd` pid, or OpenSSH raw_log field exists in this representation.

## Decision implication

`EXTERNAL_LABELED_EVALUATION` — keep separate; no direct merge.
