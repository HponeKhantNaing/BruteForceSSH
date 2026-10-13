# P10 Verification

Recorded from actual runtime after `rf-behavior-lab-v1.0.0` export.

```text
P9 integrity:
PASS

Selected model:
random_forest_behavior

Selected representation:
behavior_raw

Source model SHA-256:
6176bded24585a1599ee7644cbe15eb426fb3cd7ea803c4ed5f5f038cbd4ce69

Release model SHA-256:
6176bded24585a1599ee7644cbe15eb426fb3cd7ea803c4ed5f5f038cbd4ce69

Byte identity:
PASS

Feature count:
22

Feature-order match:
PASS

Model classes:
['BRUTE_FORCE', 'NORMAL', 'SUSPICIOUS']

TF-IDF required:
NO

Scaler required:
NO

Source/release prediction parity:
PASS

Source/release probability parity:
PASS

Bundle checksum validation:
PASS

Secret scan:
PASS

P8 unchanged:
PASS

P9 unchanged:
PASS

Retraining performed:
NO
```

Smoke prediction (packaging only, not accuracy): `SUSPICIOUS` on synthetic fixture.

Archive: `artifacts/p10/dist/rf-behavior-lab-v1.0.0.tar.gz`
