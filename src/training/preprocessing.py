"""TRAIN-only TF-IDF / scaler fitting and hybrid matrix construction."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler

from features.text_features import build_tfidf_vectorizer


def fit_tfidf_train_only(
    train_texts: list[str],
    p7_config: dict[str, Any],
) -> TfidfVectorizer:
    """Fit TF-IDF on TRAIN texts only. Never pass val/test texts here."""
    vec = build_tfidf_vectorizer(p7_config)
    vec.fit(train_texts)
    return vec


def transform_text(vectorizer: TfidfVectorizer, texts: list[str]) -> sparse.spmatrix:
    return vectorizer.transform(texts)


def fit_scaler_train_only(X_train: np.ndarray) -> StandardScaler:
    """Fit StandardScaler on TRAIN behavioral matrix only."""
    scaler = StandardScaler()
    scaler.fit(X_train)
    return scaler


def transform_behavior(scaler: StandardScaler, X: np.ndarray) -> np.ndarray:
    return scaler.transform(X)


def build_behavior_matrix(
    rows_by_id: dict[str, dict[str, Any]],
    sample_ids: list[str],
    feature_order: list[str],
) -> np.ndarray:
    mat = np.zeros((len(sample_ids), len(feature_order)), dtype=np.float64)
    for i, sid in enumerate(sample_ids):
        feats = rows_by_id[sid]["features"]
        for j, name in enumerate(feature_order):
            mat[i, j] = float(feats[name])
    return mat


def build_hybrid(X_text: sparse.spmatrix, X_behavior_scaled: np.ndarray) -> sparse.spmatrix:
    """Sparse hstack of TF-IDF + scaled behavioral features."""
    behavior_sparse = sparse.csr_matrix(X_behavior_scaled)
    return sparse.hstack([X_text, behavior_sparse], format="csr")
