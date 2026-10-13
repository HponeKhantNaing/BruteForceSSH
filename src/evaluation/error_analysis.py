"""Error / disagreement analysis helpers (evaluation metadata only)."""

from __future__ import annotations

from typing import Any


def build_error_records(
    sample_ids: list[str],
    y_true: list[str],
    y_pred: list[str],
    targets_by_id: dict[str, dict[str, Any]],
    behavioral_by_id: dict[str, dict[str, Any]],
    *,
    model_id: str,
) -> list[dict[str, Any]]:
    rows = []
    for sid, yt, yp in zip(sample_ids, y_true, y_pred):
        if yt == yp:
            continue
        feats = behavioral_by_id[sid]["features"]
        # compact snapshot of key behavior features only
        snap = {
            k: feats.get(k)
            for k in (
                "total_attempts",
                "failed_attempts",
                "successful_attempts",
                "failure_ratio",
                "max_failure_streak",
                "success_after_failure",
                "unique_users_total",
            )
            if k in feats
        }
        rows.append(
            {
                "sample_id": sid,
                "scenario_id": targets_by_id[sid].get("scenario_id"),
                "true_label": yt,
                "predicted_label": yp,
                "model_id": model_id,
                "behavioral_feature_snapshot": snap,
                "text_summary_reference": "canonical_text from P7 text_samples (normalized; no raw IP/username)",
            }
        )
    return rows


def disagreement_analysis(
    sample_ids: list[str],
    y_true: list[str],
    preds_by_model: dict[str, list[str]],
    targets_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """VALIDATION-only: where text / behavior / hybrid LR disagree."""
    keys = [
        "logistic_regression_text",
        "logistic_regression_behavior",
        "logistic_regression_hybrid",
    ]
    if not all(k in preds_by_model for k in keys):
        return []
    out = []
    for i, sid in enumerate(sample_ids):
        pt, pb, ph = (preds_by_model[k][i] for k in keys)
        if len({pt, pb, ph}) == 1:
            continue
        out.append(
            {
                "sample_id": sid,
                "scenario_id": targets_by_id[sid].get("scenario_id"),
                "true_label": y_true[i],
                "logistic_regression_text": pt,
                "logistic_regression_behavior": pb,
                "logistic_regression_hybrid": ph,
            }
        )
    return out
