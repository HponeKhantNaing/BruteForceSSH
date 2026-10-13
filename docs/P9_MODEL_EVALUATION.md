# P9 Model Evaluation

## Objective

Evaluate frozen P8 candidates on VALIDATION, select exactly one model with a predefined policy, then run a one-time locked TEST on that model only.

## P8 Frozen Inputs

Split / training manifests, TF-IDF, scaler, feature order, and six model artifacts under `artifacts/p8/`.

## Why Validation Selects the Model

TEST must remain untouched for selection. Validation is the only partition used to choose among candidates.

## Why TEST Is Not Used for Selection

Using TEST to pick the winner contaminates the final estimate. P9 forbids multi-model TEST evaluation.

## Validation Metrics

All six models scored on 15 validation samples (scenarios N04/S03/B04).

## Selection Policy

Primary: validation **macro F1**.  
Ties: minimum class recall → balanced accuracy → accuracy → config preference order.

## Selected Model

See `data/evaluation/p9/model_selection.json` (runtime result).

## Selection Lock

`model_selection.lock.json` must exist before TEST.

## Final TEST Procedure

Selected model only; receipt prevents re-runs.

## Final TEST Metrics

See `test_metrics_selected.json` (raw counts + rates).

## Confusion Matrix / Scenario-Level Results

See `test_confusion_matrix_selected.json` and `scenario_breakdown.json`.

## Text vs Behavior vs Hybrid Ablation

VALIDATION-only LR family comparison in `ablation_analysis.json`.

## Error Analysis

`error_analysis.json` — descriptive only; does not change the model.

## Model Interpretation

Optional; coefficients/importances are diagnostic. RF impurity importance is not causal.

## Small-Sample Limitation

n_val = n_test = 15; one error ≈ 6.67 pp accuracy; one class error = 20 pp recall.

## Controlled-Scenario Limitation

Each class is one held-out scenario group. Metrics ≈ scenario-family performance.

## No Real-World Generalization Claim

Even 15/15 TEST success only covers N03/S01/B01 lab scenarios.

## P10 Handoff

Package the exact selected P8 artifact + required preprocessing for its representation. Do not silently retrain.
