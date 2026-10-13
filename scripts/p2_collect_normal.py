#!/usr/bin/env python3
"""
P2 — Collect normal / benign SSH authentication logs from the project-owned Ubuntu lab.

Safety:
  - Targets 127.0.0.1 / localhost only
  - Credentials from environment (.env)
  - No passwords written to manifests/index
  - N06 allows at most one intentional failed attempt per run
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from collection.p2_normal import (  # noqa: E402
    assert_lab_ready,
    assert_localhost,
    append_jsonl,
    capture_slice,
    iso_now,
    load_credentials,
    load_dotenv_file,
    master_log_size,
    sha256_bytes,
    sha256_file,
    ssh_failed_once,
    ssh_success_session,
    summarize_auth_text,
    utc_stamp,
    verify_expected_patterns,
    wait_for_log_flush,
    write_json,
)


DEFAULT_CONFIG = ROOT / "config" / "p2_normal_scenarios.yaml"


def load_config(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid config structure in {path}")
    return data


def validate_config(cfg: dict[str, Any]) -> None:
    coll = cfg.get("collection") or {}
    host = coll.get("target_host", "127.0.0.1")
    assert_localhost(host)
    allowed = set(coll.get("allowed_hosts") or ["127.0.0.1", "localhost"])
    if host not in allowed and host.lower() not in {a.lower() for a in allowed}:
        raise RuntimeError("target_host not in allowed_hosts")

    min_gap = float(coll.get("min_gap_seconds", 3))
    scenarios = cfg.get("scenarios") or {}
    if not scenarios:
        raise RuntimeError("No scenarios defined")

    for sid, sc in scenarios.items():
        if not isinstance(sc, dict):
            raise RuntimeError(f"Scenario {sid} must be a mapping")
        reps = int(sc.get("repetitions", 1))
        if reps < 0:
            raise RuntimeError(f"{sid}: repetitions must be >= 0")
        if sid == "N06_ISOLATED_PASSWORD_MISTAKE":
            max_fail = int(sc.get("max_failed_attempts", 1))
            if max_fail != 1:
                raise RuntimeError(
                    f"{sid}: max_failed_attempts must be exactly 1 for P2 (got {max_fail})"
                )
        gap = sc.get("gap_seconds")
        if gap is not None and float(gap) < min_gap:
            raise RuntimeError(f"{sid}: gap_seconds={gap} below min_gap_seconds={min_gap}")
        rg = sc.get("reconnect_gap_seconds")
        if rg is not None and float(rg) < min_gap:
            raise RuntimeError(
                f"{sid}: reconnect_gap_seconds={rg} below min_gap_seconds={min_gap}"
            )


def make_run_id(scenario_id: str, seq: int) -> str:
    return f"{scenario_id}_{utc_stamp()}_{seq:03d}"


def scenario_dir(output_root: Path, scenario_id: str, run_id: str) -> Path:
    return output_root / scenario_id / run_id


def execute_scenario_actions(
    scenario_id: str,
    sc: dict[str, Any],
    creds,
    ssh_timeout: float,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []

    if scenario_id == "N01_SINGLE_SUCCESS":
        actions.extend(ssh_success_session(creds, commands=None, hold_seconds=0, timeout=ssh_timeout))

    elif scenario_id == "N02_COMMAND_SESSION":
        cmds = list(sc.get("commands") or ["whoami"])
        actions.extend(ssh_success_session(creds, commands=cmds, timeout=ssh_timeout))

    elif scenario_id == "N03_SHORT_SESSION":
        cmds = list(sc.get("commands") or [])
        hold = float(sc.get("duration_seconds", 3))
        actions.extend(
            ssh_success_session(creds, commands=cmds, hold_seconds=hold, timeout=ssh_timeout)
        )

    elif scenario_id == "N04_LOW_FREQUENCY_REPEAT":
        sessions = int(sc.get("sessions", 2))
        gap = float(sc.get("gap_seconds", 10))
        for i in range(sessions):
            actions.extend(ssh_success_session(creds, commands=["whoami"], timeout=ssh_timeout))
            if i < sessions - 1:
                time.sleep(gap)
                actions.append({"type": "gap", "seconds": gap, "at": iso_now()})

    elif scenario_id == "N05_SESSION_RECONNECT":
        gap = float(sc.get("reconnect_gap_seconds", 10))
        first = list(sc.get("commands_first") or ["whoami"])
        second = list(sc.get("commands_second") or ["pwd"])
        actions.extend(ssh_success_session(creds, commands=first, timeout=ssh_timeout))
        time.sleep(gap)
        actions.append({"type": "reconnect_gap", "seconds": gap, "at": iso_now()})
        actions.extend(ssh_success_session(creds, commands=second, timeout=ssh_timeout))

    elif scenario_id == "N06_ISOLATED_PASSWORD_MISTAKE":
        suffix = str(sc.get("wrong_password_suffix", "_wrong_once"))
        wrong = creds.password + suffix
        recovery = float(sc.get("recovery_delay_seconds", 5))
        actions.extend(ssh_failed_once(creds, wrong, timeout=ssh_timeout))
        time.sleep(recovery)
        actions.append({"type": "recovery_delay", "seconds": recovery, "at": iso_now()})
        actions.extend(ssh_success_session(creds, commands=["whoami"], timeout=ssh_timeout))

    else:
        raise RuntimeError(f"Unknown scenario implementation: {scenario_id}")

    return actions


def evaluate_run(
    scenario_id: str,
    sc: dict[str, Any],
    text: str,
) -> tuple[str, str, dict[str, Any]]:
    """Return (result, notes, event_summary). result is success|failed."""
    summary = summarize_auth_text(text)
    missing = verify_expected_patterns(text, list(sc.get("expected_patterns") or []))
    notes = ""

    if scenario_id == "N06_ISOLATED_PASSWORD_MISTAKE":
        fails = summary["failed_password_count"]
        if fails != 1:
            return (
                "failed",
                f"N06 expected exactly 1 Failed password line, found {fails}",
                summary,
            )
        if summary["accepted_password_count"] < 1:
            return "failed", "N06 missing successful Accepted password after recovery", summary

    if missing:
        return "failed", f"Missing expected patterns: {missing}", summary

    if not text.strip():
        return "failed", "Captured auth log slice is empty", summary

    return "success", notes, summary


def run_one(
    *,
    scenario_id: str,
    sc: dict[str, Any],
    seq: int,
    batch_id: str,
    cfg: dict[str, Any],
    creds,
    output_root: Path,
    master_log: Path,
    dry_run: bool,
) -> dict[str, Any]:
    coll = cfg["collection"]
    run_id = make_run_id(scenario_id, seq)
    out_dir = scenario_dir(output_root, scenario_id, run_id)
    if out_dir.exists():
        raise RuntimeError(f"Refusing to overwrite existing run directory: {out_dir}")

    started = iso_now()
    if dry_run:
        return {
            "run_id": run_id,
            "scenario_id": scenario_id,
            "result": "dry_run",
            "out_dir": str(out_dir.relative_to(ROOT)),
        }

    out_dir.mkdir(parents=True, exist_ok=False)
    start_offset = master_log_size(master_log)
    actions: list[dict[str, Any]] = []
    result = "success"
    notes = ""
    raw_bytes = b""
    end_offset = start_offset
    event_summary: dict[str, Any] = {}

    try:
        actions = execute_scenario_actions(
            scenario_id,
            sc,
            creds,
            float(coll.get("ssh_timeout_seconds", 20)),
        )
        end_offset = wait_for_log_flush(
            master_log,
            poll_ms=int(coll.get("log_flush_poll_ms", 250)),
            timeout_seconds=float(coll.get("log_flush_timeout_seconds", 5)),
            stable_rounds=int(coll.get("log_flush_stable_rounds", 3)),
        )
        raw_bytes = capture_slice(master_log, start_offset, end_offset)
        text = raw_bytes.decode("utf-8", errors="replace")
        result, notes, event_summary = evaluate_run(scenario_id, sc, text)
    except KeyboardInterrupt:
        result = "interrupted"
        notes = "Interrupted by user"
        end_offset = master_log_size(master_log)
        raw_bytes = capture_slice(master_log, start_offset, end_offset)
        event_summary = summarize_auth_text(raw_bytes.decode("utf-8", errors="replace"))
        raise
    except Exception as exc:
        result = "failed"
        notes = f"{type(exc).__name__}: {exc}"
        end_offset = master_log_size(master_log)
        try:
            raw_bytes = capture_slice(master_log, start_offset, end_offset)
            event_summary = summarize_auth_text(raw_bytes.decode("utf-8", errors="replace"))
        except Exception:
            raw_bytes = b""
            event_summary = {}

    ended = iso_now()
    auth_path = out_dir / "auth.log"
    auth_path.write_bytes(raw_bytes)
    digest = sha256_bytes(raw_bytes)
    line_count = len(raw_bytes.decode("utf-8", errors="replace").splitlines()) if raw_bytes else 0

    manifest = {
        "schema_version": "1.0",
        "collection_phase": "P2",
        "collection_batch_id": batch_id,
        "scenario_id": scenario_id,
        "run_id": run_id,
        "scenario_intent": "normal",
        "description": sc.get("description", ""),
        "started_at": started,
        "ended_at": ended,
        "target_host": creds.host,
        "target_port": creds.port,
        "service": "ssh",
        "auth_method": "password",
        "username_alias": creds.user,
        "expected_behavior": list(sc.get("expected_patterns") or []),
        "actions": actions,
        "result": result,
        "raw_log_file": "auth.log",
        "raw_log_line_count": line_count,
        "raw_log_sha256": digest,
        "master_log_start_offset": start_offset,
        "master_log_end_offset": end_offset,
        "data_source": "local_lab",
        "lab_container": coll.get("container_name"),
        "event_summary": event_summary,
        "notes": notes,
    }
    write_json(out_dir / "manifest.json", manifest)

    index_entry = {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "collection_batch_id": batch_id,
        "started_at": started,
        "ended_at": ended,
        "result": result,
        "raw_log_path": str((out_dir / "auth.log").relative_to(ROOT)),
        "manifest_path": str((out_dir / "manifest.json").relative_to(ROOT)),
        "raw_log_line_count": line_count,
        "raw_log_sha256": digest,
        "data_source": "local_lab",
        "scenario_intent": "normal",
    }
    append_jsonl(output_root / "index.jsonl", index_entry)

    return {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "result": result,
        "notes": notes,
        "line_count": line_count,
        "sha256": digest,
        "path": str(out_dir.relative_to(ROOT)),
    }


def select_scenarios(cfg: dict[str, Any], only: str | None) -> list[tuple[str, dict[str, Any]]]:
    scenarios = cfg.get("scenarios") or {}
    selected = []
    for sid, sc in scenarios.items():
        if only and sid != only:
            continue
        if not only and not sc.get("enabled", True):
            continue
        selected.append((sid, sc))
    if only and not selected:
        raise RuntimeError(f"Scenario not found or not selectable: {only}")
    return selected


def print_dry_run(cfg: dict[str, Any], selected: list[tuple[str, dict]], reps_override: int | None) -> None:
    coll = cfg["collection"]
    print("=== P2 dry-run ===")
    print(f"target_host: {coll.get('target_host')}")
    print(f"allowed_hosts: {coll.get('allowed_hosts')}")
    print(f"master_auth_log: {coll.get('master_auth_log')}")
    print(f"normal_output_dir: {coll.get('normal_output_dir')}")
    print(f"container: {coll.get('container_name')}")
    print("scenarios:")
    for sid, sc in selected:
        reps = reps_override if reps_override is not None else int(sc.get("repetitions", 1))
        print(f"  - {sid}: enabled={sc.get('enabled', True)} repetitions={reps}")
        print(f"    output: {coll.get('normal_output_dir')}/{sid}/<run_id>/")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P2 normal SSH auth log collection (localhost lab only)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--scenario", help="Run a single scenario id (e.g. N01_SINGLE_SUCCESS)")
    parser.add_argument("--all", action="store_true", help="Run all enabled scenarios")
    parser.add_argument("--repetitions", type=int, default=None, help="Override repetitions for selected scenarios")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-id", default=None, help="Optional batch id (default auto)")
    args = parser.parse_args(argv)

    if not args.scenario and not args.all and not args.dry_run:
        # Default to --all for convenience when no selector given
        args.all = True

    load_dotenv_file(ROOT)
    cfg = load_config(args.config)
    validate_config(cfg)

    selected = select_scenarios(cfg, args.scenario)
    if args.dry_run:
        print_dry_run(cfg, selected, args.repetitions)
        return 0

    coll = cfg["collection"]
    master_log = ROOT / coll["master_auth_log"]
    output_root = ROOT / coll["normal_output_dir"]
    output_root.mkdir(parents=True, exist_ok=True)

    creds = load_credentials(coll.get("target_host", "127.0.0.1"), coll.get("target_port"))
    assert_lab_ready(coll["container_name"], master_log, creds.host, creds.port)

    # One controlled credential validation (no retry loop)
    print("[p2] Validating credentials (single attempt)...")
    try:
        ssh_success_session(creds, commands=["true"], timeout=float(coll.get("credential_check_timeout_seconds", 15)))
    except Exception as exc:
        print(f"[p2] ERROR: credential validation failed: {exc}", file=sys.stderr)
        print("[p2] Refusing to start collection (avoids accidental failure bursts).", file=sys.stderr)
        return 2
    print("[p2] Credential validation OK")

    # Allow credential-check log lines to flush before first scenario boundary
    wait_for_log_flush(
        master_log,
        poll_ms=int(coll.get("log_flush_poll_ms", 250)),
        timeout_seconds=float(coll.get("log_flush_timeout_seconds", 5)),
        stable_rounds=int(coll.get("log_flush_stable_rounds", 3)),
    )

    batch_id = args.batch_id or f"P2_{utc_stamp()}"
    batch_started = iso_now()
    results: list[dict[str, Any]] = []
    print(f"[p2] collection_batch_id={batch_id}")

    try:
        for sid, sc in selected:
            reps = args.repetitions if args.repetitions is not None else int(sc.get("repetitions", 1))
            print(f"[p2] Scenario {sid} × {reps}")
            for i in range(1, reps + 1):
                print(f"[p2]   run {i}/{reps} ...", flush=True)
                try:
                    r = run_one(
                        scenario_id=sid,
                        sc=sc,
                        seq=i,
                        batch_id=batch_id,
                        cfg=cfg,
                        creds=creds,
                        output_root=output_root,
                        master_log=master_log,
                        dry_run=False,
                    )
                except KeyboardInterrupt:
                    print("\n[p2] Interrupted.", file=sys.stderr)
                    results.append(
                        {
                            "run_id": None,
                            "scenario_id": sid,
                            "result": "interrupted",
                            "notes": "KeyboardInterrupt",
                            "line_count": 0,
                        }
                    )
                    raise
                results.append(r)
                status = r["result"]
                print(f"[p2]   {r['run_id']}: {status}" + (f" ({r.get('notes')})" if r.get("notes") else ""))
                if status == "interrupted":
                    break
    except KeyboardInterrupt:
        pass

    batch_ended = iso_now()
    attempted = len(results)
    passed = sum(1 for r in results if r.get("result") == "success")
    failed = sum(1 for r in results if r.get("result") == "failed")
    interrupted = sum(1 for r in results if r.get("result") == "interrupted")
    total_lines = sum(int(r.get("line_count") or 0) for r in results)

    by_scenario: dict[str, dict[str, int]] = {}
    for r in results:
        sid = r.get("scenario_id") or "unknown"
        bucket = by_scenario.setdefault(sid, {"attempted": 0, "passed": 0, "failed": 0, "interrupted": 0})
        bucket["attempted"] += 1
        key = r.get("result") if r.get("result") in {"passed", "failed", "interrupted", "success"} else "failed"
        if key == "success":
            bucket["passed"] += 1
        elif key == "interrupted":
            bucket["interrupted"] += 1
        elif key == "failed":
            bucket["failed"] += 1
        else:
            bucket["failed"] += 1

    summary = {
        "collection_phase": "P2",
        "collection_batch_id": batch_id,
        "started_at": batch_started,
        "ended_at": batch_ended,
        "target_host": creds.host,
        "target_port": creds.port,
        "master_auth_log": coll["master_auth_log"],
        "normal_output_dir": coll["normal_output_dir"],
        "runs_attempted": attempted,
        "runs_passed": passed,
        "runs_failed": failed,
        "runs_interrupted": interrupted,
        "total_captured_log_lines": total_lines,
        "by_scenario": by_scenario,
        "runs": [
            {
                "run_id": r.get("run_id"),
                "scenario_id": r.get("scenario_id"),
                "result": r.get("result"),
                "path": r.get("path"),
                "notes": r.get("notes"),
            }
            for r in results
        ],
        "issues": [r.get("notes") for r in results if r.get("result") != "success" and r.get("notes")],
    }
    summary_path = output_root / f"{batch_id}_summary.json"
    write_json(summary_path, summary)
    print(f"[p2] Summary written: {summary_path.relative_to(ROOT)}")
    print(f"[p2] attempted={attempted} passed={passed} failed={failed} interrupted={interrupted}")

    return 0 if failed == 0 and interrupted == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
