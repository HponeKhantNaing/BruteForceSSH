"""P2 normal authentication log collection helpers (local lab only)."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import paramiko
from paramiko.ssh_exception import AuthenticationException, SSHException

ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost"})


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_stamp(dt: datetime | None = None) -> str:
    d = dt or utc_now()
    return d.strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return utc_now().isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_dotenv_file(root: Path) -> None:
    env_path = root / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except ImportError:
        # Minimal fallback parser
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value


@dataclass
class LabCredentials:
    user: str
    password: str
    host: str
    port: int


def load_credentials(cfg_host: str, cfg_port: int | None) -> LabCredentials:
    user = os.environ.get("LAB_SSH_USER", "").strip()
    password = os.environ.get("LAB_SSH_PASSWORD", "").strip()
    if not user or not password:
        raise RuntimeError(
            "LAB_SSH_USER and LAB_SSH_PASSWORD must be set in the environment or .env"
        )
    port_env = os.environ.get("LAB_SSH_PORT", "").strip()
    if cfg_port is not None:
        port = int(cfg_port)
    elif port_env:
        port = int(port_env)
    else:
        port = 2222
    host = (cfg_host or "127.0.0.1").strip()
    assert_localhost(host)
    if not (1 <= port <= 65535):
        raise RuntimeError(f"Invalid LAB_SSH_PORT / target_port: {port}")
    return LabCredentials(user=user, password=password, host=host, port=port)


def assert_localhost(host: str) -> None:
    normalized = host.strip().lower()
    if normalized not in ALLOWED_HOSTS:
        raise RuntimeError(
            f"Refusing to run P2 collection against a non-local target: {host!r}. "
            "Only 127.0.0.1 / localhost are allowed."
        )


def docker_container_health(container_name: str) -> tuple[str, str]:
    """Return (status, health) e.g. ('running', 'healthy')."""
    try:
        out = subprocess.check_output(
            [
                "docker",
                "inspect",
                "--format",
                "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
                container_name,
            ],
            stderr=subprocess.STDOUT,
            text=True,
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Lab container {container_name!r} not found or docker inspect failed: {exc.output}"
        ) from exc
    parts = out.split()
    status = parts[0] if parts else "unknown"
    health = parts[1] if len(parts) > 1 else "none"
    return status, health


def assert_lab_ready(container_name: str, master_log: Path, host: str, port: int) -> None:
    status, health = docker_container_health(container_name)
    if status != "running":
        raise RuntimeError(f"Lab container not running (status={status}). Start with ./scripts/lab_start.sh")
    if health not in {"healthy", "none"}:
        raise RuntimeError(f"Lab container not healthy (health={health}). Check ./scripts/lab_status.sh")
    if health == "none":
        # Still require running; warn via message only if no healthcheck — our P1 has healthcheck.
        pass
    if health != "healthy":
        raise RuntimeError(f"Lab container health is {health!r}; expected healthy.")
    if not master_log.is_file():
        raise RuntimeError(f"Master auth log missing: {master_log}")
    # Port reachability on localhost
    with socket.create_connection((host, port), timeout=3):
        pass


def make_ssh_client() -> paramiko.SSHClient:
    """Create an SSH client that never uses agent/keys by default at connect time."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    return client


# Re-export for P3 and other collectors
__all__ = [
    "ALLOWED_HOSTS",
    "LabCredentials",
    "assert_lab_ready",
    "assert_localhost",
    "append_jsonl",
    "capture_slice",
    "iso_now",
    "load_credentials",
    "load_dotenv_file",
    "make_ssh_client",
    "master_log_size",
    "sha256_bytes",
    "sha256_file",
    "ssh_failed_once",
    "ssh_success_session",
    "summarize_auth_text",
    "utc_stamp",
    "verify_expected_patterns",
    "wait_for_log_flush",
    "write_json",
]


def ssh_connect(
    creds: LabCredentials,
    password: str,
    timeout: float,
) -> paramiko.SSHClient:
    """Connect with password auth only; no agent/keys; single password attempt."""
    client = make_ssh_client()
    client.connect(
        hostname=creds.host,
        port=creds.port,
        username=creds.user,
        password=password,
        look_for_keys=False,
        allow_agent=False,
        timeout=timeout,
        auth_timeout=timeout,
        banner_timeout=timeout,
        disabled_algorithms={"auth": ["keyboard-interactive", "gssapi"]},
    )
    return client


def ssh_success_session(
    creds: LabCredentials,
    *,
    commands: list[str] | None = None,
    hold_seconds: float = 0.0,
    timeout: float = 20.0,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    client = ssh_connect(creds, creds.password, timeout)
    actions.append({"type": "ssh_connect", "result": "accepted", "at": iso_now()})
    try:
        for cmd in commands or []:
            stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            actions.append(
                {
                    "type": "exec",
                    "command": cmd,
                    "exit_code": exit_code,
                    "at": iso_now(),
                }
            )
        if hold_seconds > 0:
            time.sleep(hold_seconds)
            actions.append({"type": "hold", "seconds": hold_seconds, "at": iso_now()})
    finally:
        client.close()
        actions.append({"type": "ssh_close", "at": iso_now()})
    return actions


def ssh_failed_once(creds: LabCredentials, wrong_password: str, timeout: float = 20.0) -> list[dict[str, Any]]:
    """Exactly one intentional failed password authentication (no automatic retries)."""
    actions: list[dict[str, Any]] = []
    client = make_ssh_client()
    try:
        client.connect(
            hostname=creds.host,
            port=creds.port,
            username=creds.user,
            password=wrong_password,
            look_for_keys=False,
            allow_agent=False,
            timeout=timeout,
            auth_timeout=timeout,
            banner_timeout=timeout,
            disabled_algorithms={"auth": ["keyboard-interactive", "gssapi"]},
        )
        client.close()
        raise RuntimeError("Expected authentication failure, but SSH connect succeeded")
    except AuthenticationException:
        actions.append(
            {
                "type": "ssh_auth_failed",
                "intentional": True,
                "attempts": 1,
                "at": iso_now(),
            }
        )
    except SSHException as exc:
        # Some servers close after auth failure with a generic SSHException
        msg = str(exc).lower()
        if "auth" in msg or "permission" in msg:
            actions.append(
                {
                    "type": "ssh_auth_failed",
                    "intentional": True,
                    "attempts": 1,
                    "at": iso_now(),
                    "note": type(exc).__name__,
                }
            )
        else:
            raise
    finally:
        try:
            client.close()
        except Exception:
            pass
    return actions


def master_log_size(path: Path) -> int:
    return path.stat().st_size


def wait_for_log_flush(
    path: Path,
    *,
    poll_ms: int,
    timeout_seconds: float,
    stable_rounds: int,
) -> int:
    """Poll until file size is unchanged for stable_rounds; return final size."""
    deadline = time.monotonic() + timeout_seconds
    last = master_log_size(path)
    stable = 0
    while time.monotonic() < deadline:
        time.sleep(poll_ms / 1000.0)
        cur = master_log_size(path)
        if cur == last:
            stable += 1
            if stable >= stable_rounds:
                return cur
        else:
            stable = 0
            last = cur
    return master_log_size(path)


def capture_slice(path: Path, start_offset: int, end_offset: int) -> bytes:
    if end_offset < start_offset:
        raise RuntimeError("Invalid log offsets: end < start")
    with path.open("rb") as f:
        f.seek(start_offset)
        return f.read(end_offset - start_offset)


def count_pattern(text: str, needle: str) -> int:
    return text.lower().count(needle.lower())


def summarize_auth_text(text: str) -> dict[str, Any]:
    return {
        "contains_accepted_password": "accepted password" in text.lower(),
        "contains_failed_password": "failed password" in text.lower(),
        "contains_session_opened": "session opened" in text.lower(),
        "contains_session_closed": "session closed" in text.lower(),
        "accepted_password_count": count_pattern(text, "Accepted password"),
        "failed_password_count": count_pattern(text, "Failed password"),
        "session_opened_count": count_pattern(text, "session opened"),
        "session_closed_count": count_pattern(text, "session closed"),
    }


def verify_expected_patterns(text: str, patterns: list[str]) -> list[str]:
    missing = []
    lower = text.lower()
    for p in patterns:
        if p.lower() not in lower:
            missing.append(p)
    return missing


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def append_jsonl(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, sort_keys=False) + "\n")
