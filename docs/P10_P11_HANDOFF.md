# P10 → P11 Handoff

## Bundle

```text
Release root:
artifacts/p10/releases/rf-behavior-lab-v1.0.0/

Model:
model/random_forest_behavior.joblib

Feature contract:
schema/feature_contract.json

Input schema:
schema/input.schema.json

Output schema:
schema/output.schema.json

Manifest:
MANIFEST.json

Checksums:
CHECKSUMS.sha256
```

## Runtime chain (P11 responsibility)

```text
Live auth.log
→ parser
→ logical attempt reconstruction
→ rolling behavioral state
→ the exact same 22 P7 features
→ P10 bundle input validation
→ Random Forest predict
→ NORMAL / SUSPICIOUS / BRUTE_FORCE
```

## Critical parity rules

1. `failed_attempts` uses **logical authentication attempts** (PAM+AUTH_FAILURE = 1 FAILURE), never double-count lines.
2. Windows: inclusive closed `[t-W, t]` for 30s / 60s / 300s (same as P7).
3. Model expects **raw** behavior features — no StandardScaler, no TF-IDF.
4. Training unit was `one contextual run = one sample`. P11 must define continuous-stream context/session policy **without** redefining feature semantics.
5. Probabilities are **uncalibrated**; no custom probability thresholds were frozen in P10.

## Explicit non-claims

P10 completion means the model bundle is packaged and validated.  
It does **not** mean real-time monitoring is complete.
