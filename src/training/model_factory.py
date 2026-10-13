"""Fixed-configuration model factories for P8 (no hyperparameter search)."""

from __future__ import annotations

from typing import Any

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC


def build_model(model_id: str, cfg: dict[str, Any], random_seed: int = 42) -> Any:
    m = cfg.get("models", {}).get(model_id) or cfg
    if model_id.startswith("logistic_regression"):
        return LogisticRegression(
            C=float(m.get("C", 1.0)),
            max_iter=int(m.get("max_iter", 2000)),
            random_state=random_seed,
            class_weight=None,
        )
    if model_id == "linear_svm_hybrid":
        return LinearSVC(
            C=float(m.get("C", 1.0)),
            max_iter=int(m.get("max_iter", 2000)),
            random_state=random_seed,
            class_weight=None,
            dual="auto",
        )
    if model_id == "multinomial_nb_text":
        return MultinomialNB(alpha=float(m.get("alpha", 1.0)))
    if model_id == "random_forest_behavior":
        return RandomForestClassifier(
            n_estimators=int(m.get("n_estimators", 200)),
            max_depth=int(m.get("max_depth", 5)),
            min_samples_leaf=int(m.get("min_samples_leaf", 2)),
            random_state=random_seed,
            n_jobs=-1,
        )
    raise ValueError(f"Unknown model_id: {model_id}")


def model_supports(model: Any) -> dict[str, bool]:
    return {
        "predict_proba": hasattr(model, "predict_proba"),
        "decision_function": hasattr(model, "decision_function"),
    }


ENABLED_MODEL_IDS = [
    "logistic_regression_hybrid",
    "logistic_regression_text",
    "logistic_regression_behavior",
    "linear_svm_hybrid",
    "multinomial_nb_text",
    "random_forest_behavior",
]
