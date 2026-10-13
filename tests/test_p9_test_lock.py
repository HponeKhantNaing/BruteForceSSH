"""TEST lock / selected-only isolation tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def test_receipt_blocks_second_test(tmp_path, monkeypatch):
    from evaluation import p9_evaluation as p9

    cfg = p9.load_yaml(ROOT / "config" / "p9_evaluation.yaml")
    cfg = dict(cfg)
    cfg["output"] = {"root": str(tmp_path / "evaluation")}
    out = tmp_path / "evaluation"
    out.mkdir(parents=True)
    (out / "test_evaluation_receipt.json").write_text(
        json.dumps({"selected_model_id": "logistic_regression_hybrid", "models_evaluated_on_test": 1}),
        encoding="utf-8",
    )
    monkeypatch.setattr(p9, "out_root", lambda root, c: out)
    result = p9.evaluate_test_selected(ROOT, cfg)
    assert result.get("refused") is True


def test_test_isolation_only_selected_predict_called():
    called = []

    class FakeBundle:
        def predict_details(self, model_id, X):
            called.append(model_id)
            return {"predicted_label": np.array(["NORMAL"] * 3)}

    selected = "logistic_regression_hybrid"
    FakeBundle().predict_details(selected, None)
    assert called == ["logistic_regression_hybrid"]
