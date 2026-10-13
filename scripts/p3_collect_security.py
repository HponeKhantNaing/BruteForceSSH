#!/usr/bin/env python3
"""
P3 — Collect controlled suspicious / brute-force-like SSH auth logs (localhost lab only).

Safety:
  - 127.0.0.1 / localhost only (no --host / --target)
  - Hard attempt / username / delay / timeout ceilings in code
  - Sequential attempts only
  - No password lists, scanning, or remote targeting
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from collection.p2_normal import (  # noqa: E402
    assert_lab_ready,
    append_jsonl,
    capture_slice,
    iso_now,
    load_credentials,
    load_dotenv_file,
    master_log_size,
    sha256_bytes,
    ssh_success_session,
    utc_stamp,
    wait_for_log_flush,
    write_json,
)
from collection.p3_security import (  # noqa: E402
    MAX_AUTH_ATTEMPTS_PER_RUN,
    MAX_SCENARIO_SECONDS,
    MAX_USERNAMES_PER_RUN,
    MIN_INTER_ATTEMPT_DELAY,
    assert_p3_localhost,
    build_attempt_sequence,
    ensure_p3_lab_users,
    evaluate_security_run,
    execute_attempt_sequence,
    validate_scenario_safety,
)

DEFAULT_CONFIG = ROOT / "config" / "p3_security_scenarios.yaml"


def load_config(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid config: {path}")
    return data


def all_scenarios(cfg: dict[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    """Map scenario_id -> (intent, config)."""
    out: dict[str, tuple[str, dict[str, Any]]] = {}
    for sid, sc in (cfg.get("suspicious_scenarios") or {}).items():
        out[sid] = ("suspicious", sc)
    for sid, sc in (cfg.get("brute_force_scenarios") or {}).items():
        out[sid] = ("brute_force", sc)
    return out


def validate_config(cfg: dict[str, Any], primary_user: str) -> None:
    coll = cfg.get("collection") or {}
    host = coll.get("target_host", "127.0.0.1")
    assert_p3_localhost(host)
    scenarios = all_scenarios(cfg)
    if not scenarios:
        raise RuntimeError("No P3 scenarios defined")
    for sid, (_intent, sc) in scenarios.items():
        if not isinstance(sc, dict):
            raise RuntimeError(f"{sid} must be a mapping")
        if int(sc.get("repetitions", 1)) < 0:
            raise RuntimeError(f"{sid}: invalid repetitions")
        validate_scenario_safety(sid, sc, primary_user=primary_user)


def select_scenarios(
    cfg: dict[str, Any],
    *,
    only: str | None,
    group: str | None,
) -> list[tuple[str, str, dict[str, Any]]]:
    selected: list[tuple[str, str, dict[str, Any]]] = []
    for sid, (intent, sc) in all_scenarios(cfg).items():
        if only and sid != only:
            continue
        if group == "suspicious" and intent != "suspicious":
            continue
        if group in {"brute-force", "brute_force"} and intent != "brute_force":
            continue
        if not only and not sc.get("enabled", True):
            continue
        selected.append((sid, intent, sc))
    if only and not selected:
        raise RuntimeError(f"Scenario not found: {only}")
    if group and not selected:
        raise RuntimeError(f"No enabled scenarios for group={group}")
    return selected


def make_run_id(scenario_id: str, seq: int) -> str:
    return f"{scenario_id}_{utc_stamp()}_{seq:03d}"


def run_one(
    *,
    scenario_id: str,
    intent: str,
    sc: dict[str, Any],
    seq: int,
    batch_id: str,
    cfg: dict[str, Any],
    creds,
    output_root: Path,
    master_log: Path,
) -> dict[str, Any]:
    coll = cfg["collection"]
    run_id = make_run_id(scenario_id, seq)
    group_dir = "suspicious" if intent == "suspicious" else "brute_force"
    out_dir = output_root / group_dir / scenario_id / run_id
    if out_dir.exists():
        raise RuntimeError(f"Refusing to overwrite existing run directory: {out_dir}")

    meta = validate_scenario_safety(scenario_id, sc, primary_user=creds.user)
    plans = build_attempt_sequence(scenario_id, sc, creds.user)
    started = iso_now()
    out_dir.mkdir(parents=True, exist_ok=False)

    start_offset = master_log_size(master_log)
    actions: list[dict[str, Any]] = []
    result = "success"
    notes = ""
    raw_bytes = b""
    end_offset = start_offset
    executed_fail = 0
    executed_ok = 0
    duration = 0.0
    event_summary: dict[str, Any] = {}

    try:
        actions, executed_fail, executed_ok, duration = execute_attempt_sequence(
            scenario_id,
            sc,
            creds,
            plans,
            ssh_timeout=float(coll.get("ssh_timeout_seconds", 20)),
        )
        end_offset = wait_for_log_flush(
            master_log,
            poll_ms=int(coll.get("log_flush_poll_ms", 250)),
            timeout_seconds=float(coll.get("log_flush_timeout_seconds", 5)),
            stable_rounds=int(coll.get("log_flush_stable_rounds", 3)),
        )
        raw_bytes = capture_slice(master_log, start_offset, end_offset)
        text = raw_bytes.decode("utf-8", errors="replace")
        result, notes, event_summary = evaluate_security_run(
            sc, text, executed_fail=executed_fail, executed_ok=executed_ok
        )
    except KeyboardInterrupt:
        result = "interrupted"
        notes = "Interrupted by user"
        end_offset = master_log_size(master_log)
        raw_bytes = capture_slice(master_log, start_offset, end_offset)
        event_summary = {}
        raise
    except Exception as exc:
        result = "failed"
        notes = f"{type(exc).__name__}: {exc}"
        end_offset = master_log_size(master_log)
        try:
            raw_bytes = capture_slice(master_log, start_offset, end_offset)
            text = raw_bytes.decode("utf-8", errors="replace")
            _, _, event_summary = evaluate_security_run(
                sc, text, executed_fail=executed_fail, executed_ok=executed_ok
            )
        except Exception:
            raw_bytes = b""
            event_summary = {}

    ended = iso_now()
    (out_dir / "auth.log").write_bytes(raw_bytes)
    digest = sha256_bytes(raw_bytes)
    line_count = len(raw_bytes.decode("utf-8", errors="replace").splitlines()) if raw_bytes else 0

    manifest = {
        "schema_version": "1.0",
        "collection_phase": "P3",
        "collection_batch_id": batch_id,
        "scenario_id": scenario_id,
        "run_id": run_id,
        "scenario_intent": intent,
        "description": sc.get("description", ""),
        "started_at": started,
        "ended_at": ended,
        "target_host": creds.host,
        "target_port": creds.port,
        "service": "ssh",
        "auth_method": "password",
        "data_source": "local_lab",
        "lab_container": coll.get("container_name"),
        "configured_attempt_count": meta["planned_auth_attempts"],
        "executed_attempt_count": executed_fail + executed_ok,
        "planned_failed_attempts": sum(1 for p in plans if not p.use_valid_password),
        "actual_failed_attempts": executed_fail,
        "planned_successes": sum(1 for p in plans if p.use_valid_password),
        "actual_successes": executed_ok,
        "configured_user_count": len(meta["usernames"]),
        "configured_usernames": meta["usernames"],
        "configured_gap_seconds": meta["gap_seconds"],
        "observed_duration_seconds": round(duration, 3),
        "safety_ceilings": {
            "MAX_AUTH_ATTEMPTS_PER_RUN": MAX_AUTH_ATTEMPTS_PER_RUN,
            "MAX_USERNAMES_PER_RUN": MAX_USERNAMES_PER_RUN,
            "MAX_SCENARIO_SECONDS": MAX_SCENARIO_SECONDS,
            "MIN_INTER_ATTEMPT_DELAY": MIN_INTER_ATTEMPT_DELAY,
        },
        "actions": actions,
        "result": result,
        "raw_log_file": "auth.log",
        "raw_log_line_count": line_count,
        "raw_log_sha256": digest,
        "master_log_start_offset": start_offset,
        "master_log_end_offset": end_offset,
        "event_summary": event_summary,
        "notes": notes,
    }
    write_json(out_dir / "manifest.json", manifest)

    index_entry = {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "scenario_intent": intent,
        "collection_batch_id": batch_id,
        "started_at": started,
        "ended_at": ended,
        "result": result,
        "raw_log_path": str((out_dir / "auth.log").relative_to(ROOT)),
        "manifest_path": str((out_dir / "manifest.json").relative_to(ROOT)),
        "raw_log_line_count": line_count,
        "raw_log_sha256": digest,
        "executed_attempt_count": executed_fail + executed_ok,
        "data_source": "local_lab",
    }
    append_jsonl(output_root / "index.jsonl", index_entry)

    return {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "scenario_intent": intent,
        "result": result,
        "notes": notes,
        "line_count": line_count,
        "executed_attempt_count": executed_fail + executed_ok,
        "path": str(out_dir.relative_to(ROOT)),
        "duration": duration,
        "failed_events": (event_summary or {}).get("auth_failure_event_count"),
    }


def print_dry_run(cfg: dict[str, Any], selected: list[tuple[str, str, dict]], reps: int | None) -> None:
    coll = cfg["collection"]
    print("=== P3 dry-run ===")
    print(f"target_host: {coll.get('target_host')}")
    print(f"allowed_hosts: {coll.get('allowed_hosts')}")
    print(f"security_output_dir: {coll.get('security_output_dir')}")
    print(
        "hard_ceilings: "
        f"attempts<={MAX_AUTH_ATTEMPTS_PER_RUN}, "
        f"usernames<={MAX_USERNAMES_PER_RUN}, "
        f"min_delay>={MIN_INTER_ATTEMPT_DELAY}s, "
        f"timeout<={MAX_SCENARIO_SECONDS}s"
    )
    print("NOTE: no --host/--target/--password-file options exist by design.")
    print("scenarios:")
    for sid, intent, sc in selected:
        n = reps if reps is not None else int(sc.get("repetitions", 1))
        meta_note = sc.get("failed_attempts") or sc.get("failed_attempts_per_user") or sc.get("burst_attempts")
        print(f"  - {sid} [{intent}] reps={n} key={meta_note}")
        print(f"    output: {coll.get('security_output_dir')}/{intent if intent!='brute_force' else 'brute_force'}/{sid}/<run_id>/")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="P3 controlled suspicious/brute-force-like collection (localhost only)"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--scenario", help="Single scenario id")
    parser.add_argument("--group", choices=["suspicious", "brute-force"], help="Run one intensity group")
    parser.add_argument("--all", action="store_true", help="Run all enabled scenarios")
    parser.add_argument("--repetitions", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-id", default=None)
    # Explicitly reject attack-CLI style options if someone tries them via unknown args? argparse does that.
    args = parser.parse_args(argv)

    # Refuse any attempt to smuggle remote targeting via env misuse in this CLI.
    # Host always comes from config and must be localhost.

    if not args.scenario and not args.group and not args.all and not args.dry_run:
        args.all = True

    load_dotenv_file(ROOT)
    cfg = load_config(args.config)
    coll = cfg["collection"]
    # Provisional credentials for validation of usernames
    provisional_user = __import__("os").environ.get("LAB_SSH_USER", "testuser")
    validate_config(cfg, provisional_user)

    selected = select_scenarios(cfg, only=args.scenario, group=args.group)
    if args.dry_run:
        print_dry_run(cfg, selected, args.repetitions)
        return 0

    master_log = ROOT / coll["master_auth_log"]
    output_root = ROOT / coll["security_output_dir"]
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "suspicious").mkdir(exist_ok=True)
    (output_root / "brute_force").mkdir(exist_ok=True)

    creds = load_credentials(coll.get("target_host", "127.0.0.1"), coll.get("target_port"))
    assert_p3_localhost(creds.host)
    assert_lab_ready(coll["container_name"], master_log, creds.host, creds.port)

    # Ensure multi-user lab accounts exist (project container only)
    extra = list(coll.get("p3_lab_users") or [])
    needed = set(extra)
    for _sid, _intent, sc in selected:
        for u in sc.get("usernames") or []:
            if u != "primary":
                needed.add(u)
    if needed:
        print(f"[p3] Ensuring lab users exist: {sorted(needed)}")
        ensure_p3_lab_users(coll["container_name"], sorted(needed), creds.password)

    print("[p3] Credential validation (single success attempt)...")
    try:
        ssh_success_session(
            creds,
            commands=["true"],
            timeout=float(coll.get("credential_check_timeout_seconds", 15)),
        )
    except Exception as exc:
        print(f"[p3] ERROR: credential validation failed: {exc}", file=sys.stderr)
        return 2
    print("[p3] Credential validation OK")

    wait_for_log_flush(
        master_log,
        poll_ms=int(coll.get("log_flush_poll_ms", 250)),
        timeout_seconds=float(coll.get("log_flush_timeout_seconds", 5)),
        stable_rounds=int(coll.get("log_flush_stable_rounds", 3)),
    )

    batch_id = args.batch_id or f"P3_{utc_stamp()}"
    batch_started = iso_now()
    results: list[dict[str, Any]] = []
    print(f"[p3] collection_batch_id={batch_id}")

    try:
        for sid, intent, sc in selected:
            reps = args.repetitions if args.repetitions is not None else int(sc.get("repetitions", 1))
            print(f"[p3] Scenario {sid} [{intent}] × {reps}")
            for i in range(1, reps + 1):
                print(f"[p3]   run {i}/{reps} ...", flush=True)
                try:
                    r = run_one(
                        scenario_id=sid,
                        intent=intent,
                        sc=sc,
                        seq=i,
                        batch_id=batch_id,
                        cfg=cfg,
                        creds=creds,
                        output_root=output_root,
                        master_log=master_log,
                    )
                except KeyboardInterrupt:
                    print("\n[p3] Interrupted.", file=sys.stderr)
                    results.append(
                        {
                            "scenario_id": sid,
                            "scenario_intent": intent,
                            "result": "interrupted",
                            "notes": "KeyboardInterrupt",
                            "line_count": 0,
                            "executed_attempt_count": 0,
                        }
                    )
                    raise
                results.append(r)
                extra = f" ({r.get('notes')})" if r.get("notes") else ""
                print(f"[p3]   {r['run_id']}: {r['result']}{extra}")
    except KeyboardInterrupt:
        pass

    batch_ended = iso_now()

    def bucket(intent: str) -> dict[str, int]:
        rs = [r for r in results if r.get("scenario_intent") == intent]
        return {
            "attempted": len(rs),
            "passed": sum(1 for r in rs if r.get("result") == "success"),
            "failed": sum(1 for r in rs if r.get("result") == "failed"),
            "interrupted": sum(1 for r in rs if r.get("result") == "interrupted"),
        }

    by_scenario: dict[str, dict[str, int]] = {}
    for r in results:
        sid = r.get("scenario_id") or "unknown"
        b = by_scenario.setdefault(sid, {"attempted": 0, "passed": 0, "failed": 0, "interrupted": 0})
        b["attempted"] += 1
        if r.get("result") == "success":
            b["passed"] += 1
        elif r.get("result") == "interrupted":
            b["interrupted"] += 1
        else:
            b["failed"] += 1

    sus = bucket("suspicious")
    bf = bucket("brute_force")
    summary = {
        "collection_phase": "P3",
        "collection_batch_id": batch_id,
        "started_at": batch_started,
        "ended_at": batch_ended,
        "target_host": creds.host,
        "target_port": creds.port,
        "suspicious_runs_attempted": sus["attempted"],
        "suspicious_runs_passed": sus["passed"],
        "suspicious_runs_failed": sus["failed"],
        "brute_force_runs_attempted": bf["attempted"],
        "brute_force_runs_passed": bf["passed"],
        "brute_force_runs_failed": bf["failed"],
        "total_ssh_auth_attempts": sum(int(r.get("executed_attempt_count") or 0) for r in results),
        "total_captured_log_lines": sum(int(r.get("line_count") or 0) for r in results),
        "by_scenario": by_scenario,
        "runs": [
            {
                "run_id": r.get("run_id"),
                "scenario_id": r.get("scenario_id"),
                "scenario_intent": r.get("scenario_intent"),
                "result": r.get("result"),
                "path": r.get("path"),
                "notes": r.get("notes"),
            }
            for r in results
        ],
        "issues": [r.get("notes") for r in results if r.get("result") != "success" and r.get("notes")],
        "safety_ceilings": {
            "MAX_AUTH_ATTEMPTS_PER_RUN": MAX_AUTH_ATTEMPTS_PER_RUN,
            "MAX_USERNAMES_PER_RUN": MAX_USERNAMES_PER_RUN,
            "MAX_SCENARIO_SECONDS": MAX_SCENARIO_SECONDS,
            "MIN_INTER_ATTEMPT_DELAY": MIN_INTER_ATTEMPT_DELAY,
        },
    }
    summary_path = output_root / f"{batch_id}_summary.json"
    write_json(summary_path, summary)
    print(f"[p3] Summary: {summary_path.relative_to(ROOT)}")
    print(
        f"[p3] suspicious passed={sus['passed']}/{sus['attempted']} "
        f"brute_force passed={bf['passed']}/{bf['attempted']}"
    )
    failed = sus["failed"] + bf["failed"] + sus["interrupted"] + bf["interrupted"]
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
