"""Auth log line parsing for P6 (observed OpenSSH / PAM formats)."""

from __future__ import annotations

import re
from typing import Any

# Observed ISO timestamp prefix from lab container auth.log
ISO_PREFIX = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)\s+"
)
HOST_PROC = re.compile(
    r"^(?P<host>\S+)\s+(?P<process>sshd)\[(?P<pid>\d+)\]:\s+(?P<msg>.*)$"
)
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
PORT = re.compile(r"\bport\s+(\d+)\b", re.IGNORECASE)

# Username extraction patterns (observed)
USER_PATTERNS = [
    re.compile(r"\bFailed password for invalid user (?P<user>\S+)\b", re.I),
    re.compile(r"\bFailed password for (?P<user>\S+)\b", re.I),
    re.compile(r"\bAccepted password for (?P<user>\S+)\b", re.I),
    re.compile(r"\bsession opened for user (?P<user>[^\s(]+)", re.I),
    re.compile(r"\bsession closed for user (?P<user>\S+)\b", re.I),
    re.compile(r"\bauthenticating user (?P<user>\S+)\b", re.I),
    re.compile(r"\buser=(?P<user>\S+)\b"),
    re.compile(r"\bClose session: user (?P<user>\S+)\b", re.I),
    re.compile(r"\bStarting session:.*\bfor (?P<user>\S+)\b", re.I),
]


def parse_auth_line(raw_line: str) -> dict[str, Any]:
    """Parse one observed auth.log line into structured fields (no fabrication)."""
    line = raw_line.rstrip("\n")
    out: dict[str, Any] = {
        "timestamp_raw": None,
        "timestamp_iso": None,
        "timestamp_parse_status": "missing",
        "hostname_raw": None,
        "process": None,
        "pid": None,
        "message": line,
        "source_ip": None,
        "source_port": None,
        "username_raw": None,
        "parse_status": "partial",
    }

    rest = line
    m_ts = ISO_PREFIX.match(line)
    if m_ts:
        out["timestamp_raw"] = m_ts.group("ts")
        out["timestamp_iso"] = m_ts.group("ts")
        out["timestamp_parse_status"] = "ok"
        rest = line[m_ts.end() :]
    else:
        out["timestamp_parse_status"] = "ambiguous"

    m_hp = HOST_PROC.match(rest)
    if m_hp:
        out["hostname_raw"] = m_hp.group("host")
        out["process"] = m_hp.group("process")
        out["pid"] = int(m_hp.group("pid"))
        out["message"] = m_hp.group("msg")
        out["parse_status"] = "matched"
    else:
        out["message"] = rest
        out["parse_status"] = "partial"

    msg = out["message"] or ""

    # Prefer client "from <ip>" / "Connection from <ip>" over local bind address
    m_from = re.search(r"\b(?:from|Connection from)\s+(\d{1,3}(?:\.\d{1,3}){3})\b", msg)
    if m_from:
        out["source_ip"] = m_from.group(1)
    else:
        ips = IPV4.findall(msg)
        if ips:
            # Skip obvious non-client placeholders when alternatives exist
            for ip in ips:
                if ip not in ("0.0.0.0", "127.0.0.1"):
                    out["source_ip"] = ip
                    break
            if out["source_ip"] is None and ips:
                out["source_ip"] = ips[0]

    m_port = PORT.search(msg)
    if m_port:
        out["source_port"] = int(m_port.group(1))

    for pat in USER_PATTERNS:
        m = pat.search(msg)
        if m:
            user = m.group("user")
            # pam_unix sometimes has user= with empty; skip empty
            if user and user not in ("=", "-"):
                out["username_raw"] = user
                break

    return out
