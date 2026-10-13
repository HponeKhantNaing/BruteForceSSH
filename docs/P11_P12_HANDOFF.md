# P11 → P12 Handoff

## Streams

```text
Prediction stream:
data/runtime/p11/predictions.jsonl

Runtime event stream:
data/runtime/p11/runtime_events.jsonl

Runtime status:
data/runtime/p11/status.json

Release ID:
rf-behavior-lab-v1.0.0
```

## Example prediction (sanitized)

```json
{
  "release_id": "rf-behavior-lab-v1.0.0",
  "episode_id": "EP_SRC_RUNTIME_001_001",
  "source_id": "SRC_RUNTIME_001",
  "snapshot_type": "ACTIVE_PREFIX",
  "provisional": true,
  "predicted_label": "SUSPICIOUS",
  "class_probabilities": {
    "NORMAL": 0.10,
    "SUSPICIOUS": 0.81,
    "BRUTE_FORCE": 0.09
  },
  "probability_type": "uncalibrated",
  "timestamp": "..."
}
```

## P12 responsibilities

- Dashboard presentation (Mobbin-inspired UI later)
- Discord alert policy, cooldown, deduplication
- Whether alerts use `ACTIVE_PREFIX`, `EPISODE_FINAL`, or both

## P12 must NOT

- Reparse raw SSH logs for classification
- Reinterpret `model.classes_` order
- Retrain / refit the model
- Perform blocking/banning

P11 does not perform prevention or blocking.
