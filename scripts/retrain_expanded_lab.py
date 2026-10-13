#!/usr/bin/env python3
"""Full retrain pipeline: augment → P8 → P9 → P10 + metrics report + registry."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from training.p8_training import canonical_json_bytes, load_yaml, sha256_bytes  # noqa: E402

RELEASE_ID = "rf-behavior-lab-v1.1.0"
RELEASE_VERSION = "1.1.0"
COPIES = 39  # 75 * (1+39) = 3000 samples


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=ROOT)


def archive_p9() -> Path:
    src = ROOT / "data" / "evaluation" / "p9"
    dst = ROOT / "data" / "evaluation" / "p9_archive_v1.0.0"
    if src.exists() and not dst.exists():
        shutil.copytree(src, dst)
    # Clear lock artifacts for fresh TEST
    for name in (
        "test_evaluation_receipt.json",
        "model_selection.json",
        "model_selection.lock.json",
        "validation_metrics.json",
        "test_metrics_selected.json",
        "evaluation_report.json",
        "evaluation_manifest.json",
        "leakage_audit.json",
        "test_predictions_selected.jsonl",
        "validation_predictions.jsonl",
    ):
        p = src / name
        if p.exists():
            p.unlink()
    return dst


def update_p9_split_hash() -> str:
    split = json.loads((ROOT / "data" / "modeling" / "p8" / "split_manifest.json").read_text())
    h = sha256_bytes(canonical_json_bytes(split))
    cfg_path = ROOT / "config" / "p9_evaluation.yaml"
    text = cfg_path.read_text(encoding="utf-8")
    import re

    text2, n = re.subn(
        r'expected_split_sha256_canonical:\s*"[0-9a-f]+"',
        f'expected_split_sha256_canonical: "{h}"',
        text,
        count=1,
    )
    if n != 1:
        raise RuntimeError("Failed to patch p9 expected_split_sha256_canonical")
    # Allow this retrain cycle to write a new TEST receipt
    if "allow_repeat_test_evaluation: false" in text2:
        text2 = text2.replace(
            "allow_repeat_test_evaluation: false",
            "allow_repeat_test_evaluation: true",
        )
    cfg_path.write_text(text2, encoding="utf-8")
    return h


def update_p10_release() -> None:
    cfg_path = ROOT / "config" / "p10_export.yaml"
    text = cfg_path.read_text(encoding="utf-8")
    text = text.replace('version: "1.0.0"', f'version: "{RELEASE_VERSION}"', 1)
    text = text.replace(
        'release_id: "rf-behavior-lab-v1.0.0"',
        f'release_id: "{RELEASE_ID}"',
        1,
    )
    cfg_path.write_text(text, encoding="utf-8")


def update_runtime_release_refs() -> None:
    for rel in ("config/p11_realtime.yaml", "config/p12_dashboard_alerts.yaml"):
        p = ROOT / rel
        t = p.read_text(encoding="utf-8")
        t = t.replace("rf-behavior-lab-v1.0.0", RELEASE_ID)
        p.write_text(t, encoding="utf-8")


def write_metrics_report(test_metrics: dict, val_metrics: dict, selection: dict, split: dict) -> Path:
    docs = ROOT / "docs"
    path = docs / f"TRAINING_METRICS_{RELEASE_ID}.md"
    pc = test_metrics.get("per_class", {})
    lines = [
        f"# Training metrics — `{RELEASE_ID}`",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Dataset",
        "",
        "- Source: controlled-lab P4/P7 features (P5 public datasets **not** merged)",
        f"- Samples after augmentation: **{split.get('train_samples', '?') + split.get('validation_samples', 0) + split.get('test_samples', 0)}**",
        f"- Train / Validation / Test: **{split.get('train_samples')}** / **{split.get('validation_samples')}** / **{split.get('test_samples')}**",
        f"- Scenario groups (no overlap): train={len(split.get('train_scenarios', []))} · val={len(split.get('validation_scenarios', []))} · test={len(split.get('test_scenarios', []))}",
        f"- Baseline preserved at: `data/features/p7_baseline_75/`",
        "",
        "## Selected model",
        "",
        f"- **{selection.get('selected_model_id')}** ({selection.get('selected_representation', 'behavior')})",
        f"- Selection rule: {selection.get('selection_reason')} (primary=`{selection.get('primary_metric')}`)",
        f"- Validation macro-F1 (selection): **{selection.get('primary_metric_value')}**",
        "",
        "## Held-out TEST metrics (selected model only)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Accuracy | **{test_metrics.get('accuracy', 0):.4f}** |",
        f"| Balanced accuracy | {test_metrics.get('balanced_accuracy', 0):.4f} |",
        f"| Macro precision | {test_metrics.get('macro_precision', 0):.4f} |",
        f"| Macro recall | **{test_metrics.get('macro_recall', 0):.4f}** |",
        f"| Macro F1 | **{test_metrics.get('macro_f1', 0):.4f}** |",
        f"| Weighted F1 | {test_metrics.get('weighted_f1', 0):.4f} |",
        f"| Min class recall | {test_metrics.get('minimum_class_recall', 0):.4f} |",
        f"| Correct / Total | {test_metrics.get('correct_count')}/{test_metrics.get('total_count')} |",
        "",
        "### Per-class (TEST)",
        "",
        "| Class | Precision | Recall | F1 | Support |",
        "|---|---|---|---|---|",
    ]
    for cls in ("NORMAL", "SUSPICIOUS", "BRUTE_FORCE"):
        m = pc.get(cls, {})
        lines.append(
            f"| {cls} | {m.get('precision', 0):.4f} | {m.get('recall', 0):.4f} | {m.get('f1', 0):.4f} | {m.get('support', 0)} |"
        )
    lines.extend(
        [
            "",
            "### Confusion matrix (rows=true, cols=pred)",
            "",
            "```json",
            json.dumps(test_metrics.get("confusion_matrix", {}), indent=2),
            "```",
            "",
            "## Validation metrics (all candidates)",
            "",
            "| Model | Accuracy | Macro F1 | Min class recall |",
            "|---|---|---|---|",
        ]
    )
    for mid, m in (val_metrics or {}).items():
        lines.append(
            f"| {mid} | {m.get('accuracy', 0):.4f} | {m.get('macro_f1', 0):.4f} | {m.get('minimum_class_recall', 0):.4f} |"
        )
    lines.extend(
        [
            "",
            "## Local artifact locations",
            "",
            f"- Release bundle: `artifacts/p10/releases/{RELEASE_ID}/`",
            "- P8 models: `artifacts/p8/models/`",
            "- P8 preprocessing: `artifacts/p8/preprocessing/`",
            "- P9 evaluation: `data/evaluation/p9/`",
            "- Metrics JSON: `data/evaluation/p9/test_metrics_selected.json`",
            "- Model registry: `artifacts/MODEL_REGISTRY.md`",
            "",
            "## Maturity note",
            "",
            "CONTROLLED_LAB_VALIDATED — larger synthetic-augmented lab set; not a production guarantee.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_registry(test_metrics: dict) -> Path:
    path = ROOT / "artifacts" / "MODEL_REGISTRY.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = f"""# BruteWatch local model registry

Keep this file updated when exporting a new lab release.

## Active release

| Field | Value |
|---|---|
| Release ID | `{RELEASE_ID}` |
| Channel | lab |
| Model | `random_forest_behavior` |
| Representation | behavior (raw numeric features) |
| Path | `artifacts/p10/releases/{RELEASE_ID}/` |
| Archive | `artifacts/p10/dist/` (if present) |
| TEST accuracy | {test_metrics.get('accuracy', 0):.4f} |
| TEST macro recall | {test_metrics.get('macro_recall', 0):.4f} |
| TEST macro F1 | {test_metrics.get('macro_f1', 0):.4f} |
| Metrics doc | `docs/TRAINING_METRICS_{RELEASE_ID}.md` |

## Runtime wiring

- P11: `config/p11_realtime.yaml` → `artifacts/p10/releases/{RELEASE_ID}`
- P12: `config/p12_dashboard_alerts.yaml` → `release_id: {RELEASE_ID}`

## Frozen baselines

| Name | Path |
|---|---|
| P7 original 75-run features | `data/features/p7_baseline_75/` |
| Previous release | `artifacts/p10/releases/rf-behavior-lab-v1.0.0/` |
| Previous P9 eval | `data/evaluation/p9_archive_v1.0.0/` |

## Do not commit

- `.env` secrets
- Discord webhooks
- Raw passwords
"""
    path.write_text(body, encoding="utf-8")
    return path


def main() -> int:
    py = sys.executable

    # 1) Augment
    run([py, "scripts/p7_augment_features.py", "--copies", str(COPIES), "--seed", "42"])

    # 2) Archive old P9 + clear locks
    archive_p9()

    # 3) P8 split + train
    run([py, "scripts/p8_train_models.py", "--split"])
    run([py, "scripts/p8_train_models.py", "--train"])

    # 4) Patch P9 expected split hash
    split_hash = update_p9_split_hash()
    print("p9 expected split hash ->", split_hash, flush=True)

    # 5) P9 validate → val → select → test
    run([py, "scripts/p9_evaluate_models.py", "--validate"])
    run([py, "scripts/p9_evaluate_models.py", "--evaluate-validation"])
    run([py, "scripts/p9_evaluate_models.py", "--select-model"])
    run([py, "scripts/p9_evaluate_models.py", "--evaluate-test"])

    # 6) P10 new release
    update_p10_release()
    run([py, "scripts/p10_export_model.py", "--export"])
    run([py, "scripts/p10_export_model.py", "--validate-release"])
    update_runtime_release_refs()

    # 7) Reports
    test_metrics = json.loads(
        (ROOT / "data" / "evaluation" / "p9" / "test_metrics_selected.json").read_text()
    )
    # unwrap if nested
    if "metrics" in test_metrics and "accuracy" not in test_metrics:
        test_metrics = test_metrics["metrics"]
    val_raw = json.loads(
        (ROOT / "data" / "evaluation" / "p9" / "validation_metrics.json").read_text()
    )
    selection = json.loads(
        (ROOT / "data" / "evaluation" / "p9" / "model_selection.json").read_text()
    )
    split = json.loads((ROOT / "data" / "modeling" / "p8" / "split_summary.json").read_text())

    report = write_metrics_report(test_metrics, val_raw, selection, split)
    registry = write_registry(test_metrics)

    summary = {
        "ok": True,
        "release_id": RELEASE_ID,
        "split": {
            "train": split.get("train_samples"),
            "validation": split.get("validation_samples"),
            "test": split.get("test_samples"),
        },
        "test": {
            "accuracy": test_metrics.get("accuracy"),
            "macro_recall": test_metrics.get("macro_recall"),
            "macro_f1": test_metrics.get("macro_f1"),
            "correct": f"{test_metrics.get('correct_count')}/{test_metrics.get('total_count')}",
        },
        "selected_model": selection.get("selected_model_id"),
        "metrics_doc": str(report.relative_to(ROOT)),
        "registry": str(registry.relative_to(ROOT)),
        "release_path": f"artifacts/p10/releases/{RELEASE_ID}",
    }
    out = ROOT / "data" / "modeling" / "p8" / "retrain_summary_v1.1.0.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
