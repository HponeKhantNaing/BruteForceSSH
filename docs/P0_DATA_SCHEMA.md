# P0 — Canonical Dataset Schema

**Phase:** P0 — Project Foundation  
**Status:** Schema design only — no populated dataset in P0

---

## 1. Purpose

Define one canonical event record so collection, labeling, feature engineering, training, inference, and the dashboard API share the same field meanings.

---

## 2. Schema fields

| Field | Type (planned) | Description |
|---|---|---|
| `event_id` | string (UUID or monotonic id) | Unique identifier for one scored/logged event row |
| `timestamp` | ISO-8601 datetime (UTC preferred) | When the authentication event occurred |
| `source_id` | string | Stable grouping key for behavioral windows (often derived from source IP, but opaque to the model as a class meme) |
| `source_ip` | string | Original source IP if known; used for grouping/display, **not** as a memorized malice feature |
| `username` | string / null | Target username in the auth attempt, if present |
| `raw_log` | string | Original log line as collected |
| `clean_log` | string | Normalized text used for TF-IDF |
| `event_type` | string enum | Parsed type, e.g. `accepted_password`, `failed_password`, `invalid_user`, `auth_failure`, `session_opened`, `session_closed`, `other` |
| `failed_count_30s` | int | Failures for this `source_id` in prior 30 seconds (inclusive policy defined in feature code later) |
| `failed_count_60s` | int | Failures for this `source_id` in prior 60 seconds |
| `failed_count_5m` | int | Failures for this `source_id` in prior 5 minutes |
| `success_count_5m` | int | Successes for this `source_id` in prior 5 minutes |
| `unique_users_60s` | int | Distinct usernames attempted by this `source_id` in prior 60 seconds |
| `attempt_rate` | float | Attempts per second over the medium window |
| `time_since_previous_attempt` | float / null | Seconds since previous attempt from same `source_id`; null if first seen |
| `failure_ratio` | float | Failures / (failures + successes) in long window; define 0 when denominator is 0 in feature code |
| `label` | enum | `NORMAL` \| `SUSPICIOUS` \| `BRUTE_FORCE` |
| `scenario_id` | string | Collection/attack scenario identifier used for leakage-safe splits |
| `data_source` | enum-like string | `local_lab` \| `synthetic` \| `public:<name>` |

---

## 3. Example record (illustrative only — not real collected data)

```json
{
  "event_id": "evt_000001",
  "timestamp": "2026-09-27T06:15:01.120Z",
  "source_id": "src_lab_01",
  "source_ip": "172.18.0.5",
  "username": "alice",
  "raw_log": "Failed password for alice from 172.18.0.5 port 45210 ssh2",
  "clean_log": "failed password for user from port ssh2",
  "event_type": "failed_password",
  "failed_count_30s": 1,
  "failed_count_60s": 1,
  "failed_count_5m": 1,
  "success_count_5m": 0,
  "unique_users_60s": 1,
  "attempt_rate": 0.02,
  "time_since_previous_attempt": null,
  "failure_ratio": 1.0,
  "label": "NORMAL",
  "scenario_id": "normal_login_mistype_01",
  "data_source": "local_lab"
}
```

This example demonstrates that a failed password can be labeled `NORMAL` when behavioral evidence is weak.

---

## 4. IP address policy (critical)

### Allowed

- Use `source_ip` / `source_id` to **group** events over time for rolling windows
- Show source identity on the dashboard for operator investigation
- Use counts/rates derived from that grouping as features

### Forbidden training pattern

Do not allow the model to learn a shortcut such as:

```text
192.168.x.x = malicious
```

or

```text
this lab IP always means BRUTE_FORCE
```

### Mitigations (planned)

1. Prefer opaque `source_id` for grouping when exporting training matrices if needed
2. Do not one-hot encode raw IP as a primary sparse feature for V1
3. Emphasize window aggregates and cleaned text
4. Split by `scenario_id`, not by “all events from IP X in train”
5. Optionally mask IPs inside `clean_log` text while preserving structured grouping fields

---

## 5. Alignment with runtime detection events

Dashboard / API detection payloads (P11–P12) should reuse the same semantics for overlapping fields, e.g.:

```json
{
  "timestamp": "...",
  "source": "...",
  "event_type": "...",
  "prediction": "SUSPICIOUS",
  "confidence": 0.82,
  "failed_count_60s": 5,
  "unique_users_60s": 3,
  "raw_log": "..."
}
```

Training schema uses `label`; runtime uses `prediction` + `confidence`. Feature fields should remain comparable.

---

## 6. Storage formats (planned)

- Raw: text logs / JSONL dumps under `data/raw/`
- Interim: JSONL or Parquet under `data/interim/`
- Processed: tabular train/val/test under `data/processed/`

Exact file naming is deferred to P6.
