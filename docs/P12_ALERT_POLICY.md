# P12 Alert Policy (`p12-alert-v1`)

| Snapshot | Label | Dashboard | Discord | Severity |
|---|---|---|---|---|
| ACTIVE_PREFIX | NORMAL | YES | NO | INFO |
| ACTIVE_PREFIX | SUSPICIOUS | YES | NO | WARNING / provisional |
| ACTIVE_PREFIX | BRUTE_FORCE | YES | NO by default | CRITICAL / provisional |
| EPISODE_FINAL | NORMAL | YES | NO | INFO |
| EPISODE_FINAL | SUSPICIOUS | YES | YES | WARNING |
| EPISODE_FINAL | BRUTE_FORCE | YES | YES | CRITICAL |

```text
probability thresholds are not used
```

Optional `early_brute_force.enabled` (default **false**) may send provisional early BRUTE_FORCE after N consecutive ACTIVE_PREFIX BRUTE_FORCE predictions — messages must say **PROVISIONAL EARLY WARNING**.

Cooldown: 60 seconds per source (same-severity suppressed; higher severity escalates).
