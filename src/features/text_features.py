"""Unfitted TF-IDF factory for P7 (fit only in P8 on TRAIN)."""

from __future__ import annotations

from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler


def build_tfidf_vectorizer(config: dict[str, Any]) -> TfidfVectorizer:
    """Return an UNFITTED TfidfVectorizer from config['text_features']."""
    tf = config.get("text_features") or config
    ngram = tf.get("ngram_range") or {}
    ngram_range = (int(ngram.get("min", 1)), int(ngram.get("max", 2)))
    return TfidfVectorizer(
        lowercase=bool(tf.get("lowercase", True)),
        ngram_range=ngram_range,
        min_df=tf.get("min_df", 2),
        max_df=tf.get("max_df", 0.95),
        max_features=tf.get("max_features", 1000),
        sublinear_tf=bool(tf.get("sublinear_tf", True)),
        norm=tf.get("norm", "l2"),
    )


def build_numeric_scaler(config: dict[str, Any] | None = None) -> StandardScaler:
    """Return an UNFITTED StandardScaler (fit in P8 on TRAIN only)."""
    return StandardScaler()


def is_vectorizer_fitted(vectorizer: TfidfVectorizer) -> bool:
    return hasattr(vectorizer, "vocabulary_") and vectorizer.vocabulary_ is not None


def is_scaler_fitted(scaler: StandardScaler) -> bool:
    return hasattr(scaler, "mean_") and scaler.mean_ is not None
