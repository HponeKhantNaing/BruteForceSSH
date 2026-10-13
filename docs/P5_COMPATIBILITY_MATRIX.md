# P5 Compatibility Matrix

Project target domain: **Linux / OpenSSH host authentication logs**  
Contextual classes: **NORMAL / SUSPICIOUS / BRUTE_FORCE**  
Primary supervised source: `data/interim/p4/run_labels.jsonl`

| Dataset | Domain | SSH | Host Logs | Labels | Normal | Brute Force | Suspicious | Direct Merge? | Decision |
|---|---|---|---|---|---|---|---|---|---|
| Loghub OpenSSH | host_log | high | yes | none (UNLABELED) | unknown unlabeled | unknown unlabeled | none labeled | NO | EXTERNAL_UNLABELED_CORPUS |
| CIC-IDS2017 | network_flow / PCAP | medium (SSH-Patator) | no | attack categories on flows | benign traffic ≠ SSH auth NORMAL | SSH-Patator flows | none | NO | EXTERNAL_LABELED_EVALUATION |
| CAM-LDS | host_log multi-source | medium | yes (multi-source) | MITRE ATT&CK / scenarios | background Linux ≠ our NORMAL ontology | technique-level BF-like | none matching project SUSPICIOUS | NO | EXTERNAL_LABELED_EVALUATION |
| Loghub HDFS | HDFS DFS logs | none | no | normal/anomaly | HDFS normal | none | n/a (anomaly ≠ SUSPICIOUS) | NO | REJECT |

## Schema compatibility (summary)

| Project field | Loghub OpenSSH | CIC-IDS2017 | CAM-LDS |
|---|---|---|---|
| scenario_id | absent | absent | external scenarios only |
| run_id | absent | absent | absent |
| timestamp | reconstructable | flow timestamps | present |
| source | partial (IP in lines) | src IP | partial |
| username | often present | absent | variable |
| raw_log | present | absent (host auth) | present in log sources |
| event role | absent | absent | absent |
| contextual target | absent | incompatible | incompatible (MITRE) |

## Sequence / behavioral context

| Dataset | Event ordering | Timestamps | Session grouping | Adequate for BRUTE_FORCE behavior? |
|---|---|---|---|---|
| Loghub OpenSSH | file order | syslog | partial (pid/fields) | possible in principle, but **no labels** |
| CIC-IDS2017 | flow records | yes | flow-based | network behavior only — **wrong representation** |
| CAM-LDS | scenario logs | yes | scenario-based | technique labels ≠ our contextual class |
