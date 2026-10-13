# Loghub OpenSSH — format inspection notes (P5)

**Mode:** Documentation-based format notes (metadata-only; no full corpus download).  
**Official sources reviewed:** https://github.com/logpai/loghub , Zenodo DOI 10.5281/zenodo.1144100  
**Access date:** 2026-09-27

## Officially documented facts

- Loghub publishes an **OpenSSH** system log dataset among other service logs.
- Records are **raw OpenSSH / sshd syslog-style lines** (host authentication-related activity).
- The OpenSSH subset is commonly cited as on the order of **tens of MB** (≈70 MB class), not a multi-hundred-GB PCAP corpus.
- Loghub is intended for **AI-driven log analytics** research; **citation of Loghub** is required.
- The OpenSSH corpus as published in Loghub is **not accompanied by NORMAL / SUSPICIOUS / BRUTE_FORCE ground-truth labels** matching this project.

## Project interpretation (not official claims)

- Domain match to our V1 target (Linux/OpenSSH host auth logs) is **high**.
- Without sequence-level trusted labels, this corpus cannot become supervised ground truth.
- Deriving BRUTE_FORCE from keywords such as `Failed password` would recreate the P4 shortcut we explicitly forbade.

## Illustrative OpenSSH line shapes (generic; not from a retained Loghub file)

```text
Dec 10 06:55:46 LabSZ sshd[24200]: Failed password for invalid user webmaster from 173.234.31.186 port 38926 ssh2
Dec 10 07:07:38 LabSZ sshd[24206]: Accepted password for walt from 192.168.56.103 port 54321 ssh2
```

These shapes confirm **host-log / OpenSSH** representation, not network-flow CSV.

## Decision implication

`EXTERNAL_UNLABELED_CORPUS` — parser robustness / format diversity only.
