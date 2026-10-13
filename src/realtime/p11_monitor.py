"""P11 monitor orchestration: parity gates, context policy, live loop."""

from __future__ import annotations

import json
import math
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from export.bundle_validator import sha256_file
from features.window_features import parse_ts
from realtime.attempt_stream import StreamingAttemptReconstructor
from realtime.context_manager import ContextManager
from realtime.feature_state import compute_episode_features
from realtime.live_parser import LiveParser
from realtime.log_tailer import LogTailer
from realtime.model_runtime import ModelRuntime
from realtime.prediction_store import PredictionStore, RuntimeEventStore, StatusWriter, utc_now


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def derive_context_policy(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    """TRAIN-only idle timeout audit. Never uses TEST labels/scores."""
    split = json.loads((root / cfg["inputs"]["p8_split_manifest"]).read_text(encoding="utf-8"))
    train_ids = list(split["train"]["sample_ids"])
    attempts = load_jsonl(root / cfg["inputs"]["p6_attempts"])
    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for a in attempts:
        by_run[a["run_id"]].append(a)

    gaps: list[float] = []
    per_run_max: list[float] = []
    for sid in train_ids:
        rid = sid.removeprefix("P6_")
        ats = sorted(by_run.get(rid, []), key=lambda x: (x.get("attempt_order") or 0, x.get("started_at") or ""))
        times = [parse_ts(a.get("started_at")) for a in ats]
        times = [t for t in times if t is not None]
        run_gaps = []
        for i in range(1, len(times)):
            g = max((times[i] - times[i - 1]).total_seconds(), 0.0)
            run_gaps.append(g)
            gaps.append(g)
        per_run_max.append(max(run_gaps) if run_gaps else 0.0)

    train_max = max(gaps) if gaps else 0.0
    configured_idle = float(cfg["context"]["idle_timeout_seconds"])
    max_episode = float(cfg["context"]["max_episode_duration_seconds"])
    safety = configured_idle - train_max

    if configured_idle <= train_max:
        raise RuntimeError(
            f"idle_timeout {configured_idle}s would split TRAIN runs (max gap {train_max}s)"
        )
    if max_episode > 300 and train_max <= 300:
        raise RuntimeError("max_episode_duration > 300 without TRAIN justification")

    policy = {
        "derivation_source": "TRAIN_ONLY",
        "train_sample_count": len(train_ids),
        "train_gap_count": len(gaps),
        "training_max_inter_attempt_gap": train_max,
        "training_median_inter_attempt_gap": statistics.median(gaps) if gaps else 0.0,
        "training_p95_inter_attempt_gap": sorted(gaps)[int(0.95 * (len(gaps) - 1))] if gaps else 0.0,
        "training_max_of_per_run_max_gaps": max(per_run_max) if per_run_max else 0.0,
        "safety_margin_seconds": safety,
        "idle_timeout_seconds": configured_idle,
        "max_episode_duration_seconds": max_episode,
        "test_used_to_tune_context": False,
        "notes": [
            "The P9 model was evaluated with known bounded scenario-run boundaries.",
            "The P11 live episode segmentation policy is a deployment integration heuristic.",
            "P9's 15/15 TEST result does NOT validate this live segmentation policy.",
        ],
    }
    out = root / cfg["outputs"]["context_policy"]
    write_json(out, policy)
    return policy


def verify_attempt_parity(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    events = load_jsonl(root / cfg["inputs"]["p6_events"])
    expected_attempts = load_jsonl(root / cfg["inputs"]["p6_attempts"])
    by_run_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in events:
        by_run_events[e["run_id"]].append(e)

    streamer = StreamingAttemptReconstructor(
        correlation_timeout_seconds=float(cfg["attempt_reconstruction"]["correlation_timeout_seconds"])
    )
    reconstructed: list[dict[str, Any]] = []
    for rid in sorted(by_run_events):
        reconstructed.extend(streamer.flush_batch(by_run_events[rid], rid))

    def count_outcome(rows: list[dict[str, Any]], outcome: str) -> int:
        return sum(1 for a in rows if a.get("outcome") == outcome)

    exp_f = count_outcome(expected_attempts, "FAILURE")
    exp_s = count_outcome(expected_attempts, "SUCCESS")
    exp_u = count_outcome(expected_attempts, "UNKNOWN")
    act_f = count_outcome(reconstructed, "FAILURE")
    act_s = count_outcome(reconstructed, "SUCCESS")
    act_u = count_outcome(reconstructed, "UNKNOWN")

    # Per-run outcome multiset compare
    exp_by_run: dict[str, list[str]] = defaultdict(list)
    act_by_run: dict[str, list[str]] = defaultdict(list)
    for a in expected_attempts:
        exp_by_run[a["run_id"]].append(a["outcome"])
    for a in reconstructed:
        act_by_run[a["run_id"]].append(a["outcome"])
    mismatches = []
    for rid in sorted(set(exp_by_run) | set(act_by_run)):
        if sorted(exp_by_run.get(rid, [])) != sorted(act_by_run.get(rid, [])):
            mismatches.append(
                {
                    "run_id": rid,
                    "expected": sorted(exp_by_run.get(rid, [])),
                    "actual": sorted(act_by_run.get(rid, [])),
                }
            )

    report = {
        "expected_failures": exp_f,
        "actual_failures": act_f,
        "expected_successes": exp_s,
        "actual_successes": act_s,
        "expected_unknown": exp_u,
        "actual_unknown": act_u,
        "expected_total": len(expected_attempts),
        "actual_total": len(reconstructed),
        "per_run_mismatches": mismatches[:20],
        "mismatch_count": len(mismatches),
        "ok": exp_f == act_f and exp_s == act_s and exp_u == act_u and len(mismatches) == 0,
    }
    write_json(root / cfg["outputs"]["attempt_parity_report"], report)
    return report


def verify_feature_parity(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    abs_tol = float(cfg["feature_parity"]["abs_tol"])
    runs = {r["run_id"]: r for r in load_jsonl(root / cfg["inputs"]["p6_runs"])}
    seqs = {s["sample_id"]: s for s in load_jsonl(root / cfg["inputs"]["p6_sequences"])}
    attempts = load_jsonl(root / cfg["inputs"]["p6_attempts"])
    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for a in attempts:
        by_run[a["run_id"]].append(a)
    p7 = {r["sample_id"]: r["features"] for r in load_jsonl(root / cfg["inputs"]["p7_behavioral"])}

    runtime = ModelRuntime(
        root / cfg["release"]["root"],
        expected_sha256=cfg["release"].get("expected_model_sha256"),
    )
    loaded = runtime.verify_and_load()
    if not loaded.get("ok"):
        return {"ok": False, "error": "bundle load failed", "loaded": loaded}

    ordered = runtime.ordered_features
    failed_ids: list[str] = []
    per_feature_mismatch: dict[str, int] = defaultdict(int)
    max_abs = 0.0
    passed = 0

    for sample_id, expected in sorted(p7.items()):
        rid = sample_id.removeprefix("P6_")
        # run_id in P6 is without P6_ prefix typically — check
        run = runs.get(rid) or runs.get(sample_id)
        if run is None:
            # try match by sample_id field
            run = next((r for r in runs.values() if r.get("sample_id") == sample_id), None)
        if run is None:
            failed_ids.append(sample_id)
            continue
        rid = run["run_id"]
        hist = sorted(
            by_run.get(rid, []),
            key=lambda a: (a.get("attempt_order") or 0, a.get("started_at") or ""),
        )
        seq = seqs.get(sample_id)
        actual = compute_episode_features(
            hist,
            ordered_features=ordered,
            run=run,
            sequence=seq,
        )
        ok = True
        for name in ordered:
            ev = float(expected.get(name, float("nan")))
            av = float(actual.get(name, float("nan")))
            if name in {
                "has_multiple_attempts",
                "success_after_failure",
                "first_attempt_failed",
                "last_attempt_success",
            } or name.endswith("_streak") or name in {
                "total_attempts",
                "failed_attempts",
                "successful_attempts",
                "failures_before_first_success",
            }:
                match = av == ev
            else:
                match = math.isclose(av, ev, rel_tol=0.0, abs_tol=abs_tol)
            if not match:
                ok = False
                per_feature_mismatch[name] += 1
                max_abs = max(max_abs, abs(av - ev) if math.isfinite(av - ev) else max_abs)
        if ok:
            passed += 1
        else:
            failed_ids.append(sample_id)

    report = {
        "samples_checked": len(p7),
        "samples_passed": passed,
        "samples_failed": len(failed_ids),
        "per_feature_mismatch_count": dict(per_feature_mismatch),
        "max_abs_difference": max_abs,
        "failed_sample_ids": failed_ids[:50],
        "ok": passed == len(p7) and len(p7) == int(cfg["feature_parity"]["expected_samples"]),
        "ordered_features": ordered,
    }
    write_json(root / cfg["outputs"]["feature_parity_report"], report)
    return report


def verify_p10_smoke_parity(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    release = root / cfg["release"]["root"]
    smoke_in = json.loads((release / "verification/smoke_test_input.json").read_text(encoding="utf-8"))
    smoke_exp = json.loads((release / "verification/smoke_test_expected.json").read_text(encoding="utf-8"))
    runtime = ModelRuntime(release, expected_sha256=cfg["release"].get("expected_model_sha256"))
    loaded = runtime.verify_and_load()
    if not loaded.get("ok"):
        return {"ok": False, "loaded": loaded}
    pred = runtime.predict_features(smoke_in["features"])
    if not pred.get("ok"):
        return {"ok": False, "pred": pred}
    label_ok = pred["predicted_label"] == smoke_exp["predicted_label"]
    # probability parity within tight tol
    probs_ok = all(
        math.isclose(
            pred["class_probabilities"][k],
            smoke_exp["class_probabilities"][k],
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        for k in smoke_exp["class_probabilities"]
    )
    return {
        "ok": label_ok and probs_ok and runtime.fit_calls == 0,
        "predicted_label": pred["predicted_label"],
        "expected_label": smoke_exp["predicted_label"],
        "probability_parity": probs_ok,
        "fit_calls": runtime.fit_calls,
        "tfidf_used": runtime.tfidf_used,
        "scaler_used": runtime.scaler_used,
    }


def verify_parity(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    policy = derive_context_policy(root, cfg)
    attempt = verify_attempt_parity(root, cfg)
    feature = verify_feature_parity(root, cfg)
    smoke = verify_p10_smoke_parity(root, cfg)
    ok = bool(attempt.get("ok") and feature.get("ok") and smoke.get("ok"))
    return {
        "ok": ok,
        "status": "PASS" if ok else "BLOCKED",
        "context_policy": policy,
        "attempt_parity": attempt,
        "feature_parity": feature,
        "p10_smoke_parity": smoke,
    }


def dry_run(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    release = root / cfg["release"]["root"]
    runtime = ModelRuntime(release, expected_sha256=cfg["release"].get("expected_model_sha256"))
    loaded = runtime.verify_and_load()
    log_path = root / cfg["log_source"]["path"]
    return {
        "p10_bundle_verification": "PASS" if loaded.get("ok") else "FAIL",
        "selected_model": "random_forest_behavior",
        "release_id": loaded.get("release_id"),
        "feature_count": loaded.get("feature_count"),
        "log_source_path": str(log_path),
        "log_source_exists": log_path.is_file(),
        "start_mode": cfg["log_source"]["start_at"],
        "context_policy": {
            "idle_timeout_seconds": cfg["context"]["idle_timeout_seconds"],
            "max_episode_duration_seconds": cfg["context"]["max_episode_duration_seconds"],
            "group_by": cfg["context"]["group_by"],
            "derivation": "TRAIN_ONLY (see context_policy.json after --verify-parity)",
        },
        "live_monitoring_started": False,
        "loaded": loaded,
    }


def validate_runtime(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    release = root / cfg["release"]["root"]
    runtime = ModelRuntime(release, expected_sha256=cfg["release"].get("expected_model_sha256"))
    loaded = runtime.verify_and_load()
    log_path = root / cfg["log_source"]["path"]
    policy_path = root / cfg["inputs"]["p4_policy"]
    checks = {
        "bundle_ok": bool(loaded.get("ok")),
        "log_accessible": log_path.is_file(),
        "parser_policy": policy_path.is_file(),
        "feature_engine": True,
        "context_config": float(cfg["context"]["idle_timeout_seconds"]) > 0,
        "no_scaler": not bool(loaded.get("verification", {}).get("checks", {}).get("scaler_required") == "FAIL"),
        "no_tfidf": True,
    }
    return {"ok": all(checks.values()), "checks": checks, "loaded": loaded}


def _emit_prediction(
    *,
    store: PredictionStore,
    events: RuntimeEventStore,
    runtime: ModelRuntime,
    episode,
    features: dict[str, float],
    snapshot_type: str,
    final: bool,
    provisional: bool,
    event_timestamp: str | None,
    latencies: list[float],
) -> dict[str, Any] | None:
    pred = runtime.predict_features(features)
    if not pred.get("ok"):
        events.emit(
            "inference_validation_error",
            episode_id=episode.episode_id,
            detail=pred.get("detail") or pred.get("error"),
        )
        return None
    latencies.append(float(pred["latency_ms"]))
    row = {
        "schema_version": "1.0",
        "release_id": runtime.release_id,
        "episode_id": episode.episode_id,
        "source_id": episode.source_token,
        "snapshot_type": snapshot_type,
        "final": final,
        "provisional": provisional,
        "attempt_count": len(episode.attempts),
        "event_timestamp": event_timestamp,
        "predicted_label": pred["predicted_label"],
        "class_probabilities": pred["class_probabilities"],
        "probability_type": "uncalibrated",
        "close_reason": episode.close_reason,
        "emitted_at": utc_now(),
    }
    store.append(row)
    events.emit("prediction_emitted", episode_id=episode.episode_id, snapshot_type=snapshot_type)
    return row


def monitor_loop(
    root: Path,
    cfg: dict[str, Any],
    *,
    duration_seconds: float | None = 15.0,
    require_parity: bool = True,
    start_at: str | None = None,
) -> dict[str, Any]:
    if require_parity:
        parity = verify_parity(root, cfg)
        if not parity.get("ok"):
            return {"ok": False, "status": "BLOCKED", "parity": parity}

    policy = derive_context_policy(root, cfg)
    release = root / cfg["release"]["root"]
    runtime = ModelRuntime(release, expected_sha256=cfg["release"].get("expected_model_sha256"))
    loaded = runtime.verify_and_load()
    if not loaded.get("ok"):
        return {"ok": False, "status": "FAIL", "error": "bundle verification failed", "loaded": loaded}

    out_root = root / cfg["outputs"]["root"]
    out_root.mkdir(parents=True, exist_ok=True)
    preds = PredictionStore(root / cfg["outputs"]["predictions"])
    events = RuntimeEventStore(root / cfg["outputs"]["runtime_events"])
    status = StatusWriter(root / cfg["outputs"]["status"])

    parser = LiveParser(root / cfg["inputs"]["p4_policy"])
    streamer = StreamingAttemptReconstructor(
        correlation_timeout_seconds=float(cfg["attempt_reconstruction"]["correlation_timeout_seconds"])
    )
    contexts = ContextManager(
        idle_timeout_seconds=float(policy["idle_timeout_seconds"]),
        max_episode_duration_seconds=float(policy["max_episode_duration_seconds"]),
    )

    log_path = root / cfg["log_source"]["path"]
    tail_start = start_at or cfg["log_source"]["start_at"]
    tailer = LogTailer(
        log_path,
        start_at=tail_start,
        poll_interval_ms=int(cfg["log_source"]["poll_interval_ms"]),
    )

    events.emit("monitor_started", release_id=runtime.release_id, log_source=str(log_path))
    events.emit("bundle_validated", release_id=runtime.release_id, sha256=runtime.model_sha256)
    status.update(
        running=True,
        release_id=runtime.release_id,
        log_source=str(log_path.relative_to(root)),
        started_at=utc_now(),
    )

    latencies: list[float] = []
    predictions = 0
    attempts_n = 0
    errors = 0
    last_pred = None
    deadline = time.monotonic() + float(duration_seconds) if duration_seconds else None

    def handle_attempt(attempt: dict[str, Any]) -> None:
        nonlocal predictions, attempts_n, last_pred, errors
        attempts_n += 1
        ep, closed = contexts.on_attempt(attempt)
        for closed_ep in closed:
            feats = contexts.features_for(closed_ep, ordered_features=runtime.ordered_features)
            row = _emit_prediction(
                store=preds,
                events=events,
                runtime=runtime,
                episode=closed_ep,
                features=feats,
                snapshot_type="EPISODE_FINAL",
                final=True,
                provisional=False,
                event_timestamp=closed_ep.last_attempt_at,
                latencies=latencies,
            )
            if row:
                predictions += 1
                last_pred = row
            else:
                errors += 1

        if cfg["inference"].get("predict_on_completed_attempt", True):
            feats = contexts.features_for(ep, ordered_features=runtime.ordered_features)
            row = _emit_prediction(
                store=preds,
                events=events,
                runtime=runtime,
                episode=ep,
                features=feats,
                snapshot_type="ACTIVE_PREFIX",
                final=False,
                provisional=True,
                event_timestamp=attempt.get("started_at"),
                latencies=latencies,
            )
            if row:
                predictions += 1
                last_pred = row
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] {ep.source_token} {ep.episode_id} "
                    f"attempt={len(ep.attempts)} prediction={row['predicted_label']} snapshot=ACTIVE_PREFIX",
                    file=sys.stderr,
                )
            else:
                errors += 1

        status.update(
            last_log_timestamp=attempt.get("started_at"),
            last_prediction_timestamp=utc_now() if last_pred else None,
            active_episode_count=contexts.active_count(),
            logical_attempts_processed=attempts_n,
            predictions_emitted=predictions,
            errors=errors,
        )

    try:
        def _stop() -> bool:
            return deadline is not None and time.monotonic() >= deadline

        for tev in tailer.iter_events(max_idle_rounds=None, should_stop=_stop):
            if _stop():
                break
            if tev.kind in ("truncated", "replaced", "rotated"):
                events.emit("log_rotated", kind=tev.kind, detail=tev.detail)
                for closed_ep in contexts.reset_all("LOG_RESET"):
                    feats = contexts.features_for(closed_ep, ordered_features=runtime.ordered_features)
                    row = _emit_prediction(
                        store=preds,
                        events=events,
                        runtime=runtime,
                        episode=closed_ep,
                        features=feats,
                        snapshot_type="EPISODE_FINAL",
                        final=True,
                        provisional=False,
                        event_timestamp=closed_ep.last_attempt_at,
                        latencies=latencies,
                    )
                    if row:
                        predictions += 1
                streamer.reset()
                continue
            if tev.kind == "missing":
                time.sleep(0.2)
                continue

            if tev.kind == "line" and tev.line is not None:
                parsed = parser.parse_line(tev.line)
                if parsed is not None:
                    result = streamer.push(parsed)
                    for attempt in result.completed_attempts:
                        handle_attempt(attempt)

            # On idle heartbeats (and after each line), expire pending PAM + close idle episodes.
            if tev.kind in ("idle", "line"):
                expired = streamer.expire_pending()
                for attempt in expired.completed_attempts:
                    handle_attempt(attempt)
                for closed_ep in contexts.check_timeouts():
                    feats = contexts.features_for(closed_ep, ordered_features=runtime.ordered_features)
                    row = _emit_prediction(
                        store=preds,
                        events=events,
                        runtime=runtime,
                        episode=closed_ep,
                        features=feats,
                        snapshot_type="EPISODE_FINAL",
                        final=True,
                        provisional=False,
                        event_timestamp=closed_ep.last_attempt_at,
                        latencies=latencies,
                    )
                    if row:
                        predictions += 1
                        last_pred = row
                        print(
                            f"[{datetime.now().strftime('%H:%M:%S')}] {closed_ep.source_token} "
                            f"{closed_ep.episode_id} prediction={row['predicted_label']} "
                            f"snapshot=EPISODE_FINAL reason={closed_ep.close_reason}",
                            file=sys.stderr,
                        )
                        status.update(
                            last_prediction_timestamp=utc_now(),
                            active_episode_count=contexts.active_count(),
                            predictions_emitted=predictions,
                            errors=errors,
                        )
    finally:
        for closed_ep in contexts.close_all("PROCESS_STOP"):
            feats = contexts.features_for(closed_ep, ordered_features=runtime.ordered_features)
            row = _emit_prediction(
                store=preds,
                events=events,
                runtime=runtime,
                episode=closed_ep,
                features=feats,
                snapshot_type="EPISODE_FINAL",
                final=True,
                provisional=False,
                event_timestamp=closed_ep.last_attempt_at,
                latencies=latencies,
            )
            if row:
                predictions += 1
        status.update(running=False)
        events.emit("monitor_stopped", predictions=predictions, attempts=attempts_n)

    latency_report = _latency_report(latencies)
    write_json(root / cfg["outputs"]["latency_report"], latency_report)
    return {
        "ok": True,
        "status": "PASS",
        "predictions_emitted": predictions,
        "logical_attempts_processed": attempts_n,
        "errors": errors,
        "last_prediction": last_pred,
        "latency": latency_report,
        "fit_calls": runtime.fit_calls,
        "tfidf_used": runtime.tfidf_used,
        "scaler_used": runtime.scaler_used,
        "p10_sha256": runtime.model_sha256,
    }


def _latency_report(latencies: list[float]) -> dict[str, Any]:
    if not latencies:
        return {
            "count": 0,
            "min_ms": None,
            "median_ms": None,
            "p95_ms": None,
            "max_ms": None,
            "lab_p95_target_ms": 1000,
            "lab_p95_pass": False,
        }
    s = sorted(latencies)
    p95 = s[min(len(s) - 1, int(math.ceil(0.95 * len(s)) - 1))]
    return {
        "count": len(s),
        "min_ms": s[0],
        "median_ms": statistics.median(s),
        "p95_ms": p95,
        "max_ms": s[-1],
        "lab_p95_target_ms": 1000,
        "lab_p95_pass": p95 <= 1000,
    }


def replay_run(root: Path, cfg: dict[str, Any], run_id: str) -> dict[str, Any]:
    """Replay one historical P6 run's events through the live pipeline (offline)."""
    events = [e for e in load_jsonl(root / cfg["inputs"]["p6_events"]) if e["run_id"] == run_id]
    if not events:
        # allow full sample_id style
        rid = run_id.removeprefix("P6_")
        events = [e for e in load_jsonl(root / cfg["inputs"]["p6_events"]) if e["run_id"] == rid]
        run_id = rid
    if not events:
        return {"ok": False, "error": f"no events for run_id={run_id}"}

    release = root / cfg["release"]["root"]
    runtime = ModelRuntime(release, expected_sha256=cfg["release"].get("expected_model_sha256"))
    loaded = runtime.verify_and_load()
    if not loaded.get("ok"):
        return {"ok": False, "loaded": loaded}

    streamer = StreamingAttemptReconstructor(
        correlation_timeout_seconds=float(cfg["attempt_reconstruction"]["correlation_timeout_seconds"])
    )
    # Use batch for exact attempt list, then feature+predict
    attempts = streamer.flush_batch(events, run_id)
    runs = {r["run_id"]: r for r in load_jsonl(root / cfg["inputs"]["p6_runs"])}
    seqs = {s["sample_id"]: s for s in load_jsonl(root / cfg["inputs"]["p6_sequences"])}
    run = runs.get(run_id)
    sample_id = run["sample_id"] if run else f"P6_{run_id}"
    seq = seqs.get(sample_id)
    feats = compute_episode_features(
        sorted(attempts, key=lambda a: (a.get("attempt_order") or 0, a.get("started_at") or "")),
        ordered_features=runtime.ordered_features,
        run=run,
        sequence=seq,
    )
    pred = runtime.predict_features(feats)
    return {
        "ok": bool(pred.get("ok")),
        "run_id": run_id,
        "attempt_count": len(attempts),
        "outcomes": {
            "FAILURE": sum(1 for a in attempts if a["outcome"] == "FAILURE"),
            "SUCCESS": sum(1 for a in attempts if a["outcome"] == "SUCCESS"),
        },
        "features": feats,
        "prediction": pred,
    }
