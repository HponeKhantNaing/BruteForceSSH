"""Deterministic multiclass metrics for P9."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    precision_score,
    recall_score,
)


DEFAULT_CLASS_ORDER = ["NORMAL", "SUSPICIOUS", "BRUTE_FORCE"]


def compute_classification_metrics(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    *,
    class_order: Sequence[str] | None = None,
) -> dict[str, Any]:
    labels = list(class_order or DEFAULT_CLASS_ORDER)
    y_true = list(y_true)
    y_pred = list(y_pred)
    n = len(y_true)
    correct = int(sum(a == b for a, b in zip(y_true, y_pred)))

    precision, recall, f1, support = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=labels,
        average=None,
        zero_division=0,
    )
    cm = confusion_matrix(y_true, y_pred, labels=labels)

    per_class = {}
    for i, lab in enumerate(labels):
        # TP for recall display
        tp = int(cm[i, i])
        per_class[lab] = {
            "precision": float(precision[i]),
            "recall": float(recall[i]),
            "f1": float(f1[i]),
            "support": int(support[i]),
            "correct": tp,
            "correct_over_support": f"{tp}/{int(support[i])}",
        }

    min_class_recall = float(min(recall)) if len(recall) else 0.0

    return {
        "correct_count": correct,
        "total_count": n,
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "macro_precision": float(precision_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "macro_recall": float(recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0)),
        "minimum_class_recall": min_class_recall,
        "per_class": per_class,
        "confusion_matrix": {
            "class_order": labels,
            "matrix": cm.tolist(),
            "rows": "actual",
            "columns": "predicted",
        },
        "normal_recall": float(per_class["NORMAL"]["recall"]),
        "suspicious_recall": float(per_class["SUSPICIOUS"]["recall"]),
        "brute_force_recall": float(per_class["BRUTE_FORCE"]["recall"]),
    }
