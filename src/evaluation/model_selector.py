"""Deterministic validation-based model selection (predefined rules only)."""

from __future__ import annotations

from typing import Any


def select_model(
    validation_metrics: dict[str, dict[str, Any]],
    *,
    primary_metric: str = "macro_f1",
    tie_breakers: list[str] | None = None,
    exact_tie_preference: list[str] | None = None,
) -> dict[str, Any]:
    """
    Select one model from validation metrics using predefined policy.

    Higher is better for all metrics used here.
    """
    tie_breakers = list(tie_breakers or ["minimum_class_recall", "balanced_accuracy", "accuracy"])
    preference = list(
        exact_tie_preference
        or [
            "logistic_regression_hybrid",
            "logistic_regression_behavior",
            "logistic_regression_text",
            "linear_svm_hybrid",
            "multinomial_nb_text",
            "random_forest_behavior",
        ]
    )

    candidates = list(validation_metrics.keys())
    if not candidates:
        raise RuntimeError("No validation metrics for selection")

    # Sort by primary, then tie breakers, then preference index (lower = preferred)
    pref_index = {m: i for i, m in enumerate(preference)}

    def sort_key(model_id: str) -> tuple:
        m = validation_metrics[model_id]
        primary = float(m[primary_metric])
        tb = tuple(float(m[k]) for k in tie_breakers)
        # Prefer lower preference index on exact ties → negate for descending? 
        # We want highest metrics first, then lowest preference index.
        # Python sort ascending: use negative metrics, then preference index.
        return (-primary, tuple(-x for x in tb), pref_index.get(model_id, 10_000), model_id)

    ranked = sorted(candidates, key=sort_key)
    selected = ranked[0]

    # Detect whether any tie-break was needed among top after primary
    top_primary = float(validation_metrics[selected][primary_metric])
    same_primary = [m for m in candidates if float(validation_metrics[m][primary_metric]) == top_primary]
    tie_break_used = len(same_primary) > 1

    reason_parts = [f"highest validation {primary_metric}"]
    if tie_break_used:
        # find first differing tie breaker
        for tb in tie_breakers:
            vals = {m: float(validation_metrics[m][tb]) for m in same_primary}
            if len(set(vals.values())) > 1:
                reason_parts = [
                    f"primary validation {primary_metric} tied",
                    f"tie-break: higher {tb}",
                ]
                break
        else:
            reason_parts = [
                f"primary validation {primary_metric} tied",
                "exact-tie preference order from config",
            ]

    return {
        "selected_model_id": selected,
        "primary_metric": primary_metric,
        "primary_metric_value": float(validation_metrics[selected][primary_metric]),
        "minimum_class_recall": float(validation_metrics[selected]["minimum_class_recall"]),
        "tie_break_used": tie_break_used,
        "tie_break_values": {
            k: float(validation_metrics[selected][k]) for k in tie_breakers
        },
        "ranked_model_ids": ranked,
        "selection_reason": "; ".join(reason_parts),
        "selection_rule_version": "p9-selection-v1",
    }
