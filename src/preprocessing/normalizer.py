"""Deterministic text normalization and identity anonymization for P6."""

from __future__ import annotations

import re
from typing import Any

IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
PID_BRACKET = re.compile(r"\bsshd\[\d+\]")
PORT_NUM = re.compile(r"\bport\s+\d+\b", re.IGNORECASE)
ISO_TS = re.compile(
    r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\b"
)
WHITESPACE = re.compile(r"\s+")


class IdentityMapper:
    """Deterministic USR_### / SRC_### assignment (sorted unique values)."""

    def __init__(self, user_prefix: str = "USR_", source_prefix: str = "SRC_", pad: int = 3):
        self.user_prefix = user_prefix
        self.source_prefix = source_prefix
        self.pad = pad
        self._users: dict[str, str] = {}
        self._sources: dict[str, str] = {}
        self._pending_users: set[str] = set()
        self._pending_sources: set[str] = set()
        self._frozen = False

    def observe_user(self, username: str | None) -> None:
        if username:
            self._pending_users.add(username)

    def observe_source(self, ip: str | None) -> None:
        if ip:
            self._pending_sources.add(ip)

    def freeze(self) -> None:
        if self._frozen:
            return
        for i, u in enumerate(sorted(self._pending_users), start=1):
            self._users[u] = f"{self.user_prefix}{i:0{self.pad}d}"
        for i, s in enumerate(sorted(self._pending_sources), start=1):
            self._sources[s] = f"{self.source_prefix}{i:0{self.pad}d}"
        self._frozen = True

    def user_id(self, username: str | None) -> str | None:
        if not username:
            return None
        self.freeze()
        return self._users.get(username)

    def source_id(self, ip: str | None) -> str | None:
        if not ip:
            return None
        self.freeze()
        return self._sources.get(ip)

    @property
    def user_count(self) -> int:
        self.freeze()
        return len(self._users)

    @property
    def source_count(self) -> int:
        self.freeze()
        return len(self._sources)


def normalize_message(
    raw_line: str,
    *,
    username: str | None = None,
    hostname: str | None = None,
    lowercase: bool = True,
) -> tuple[str, dict[str, int]]:
    """
    Produce model-eligible normalized message text.
    Returns (normalized_text, replacement_counts).
    """
    counts = {
        "timestamps": 0,
        "ips": 0,
        "ports": 0,
        "pids": 0,
        "usernames": 0,
        "hostnames": 0,
    }
    text = raw_line

    # Strip leading ISO timestamp if present (already structured elsewhere)
    text2, n = ISO_TS.subn("<TIMESTAMP>", text, count=1)
    if n:
        counts["timestamps"] += n
        # Prefer removing leading timestamp token entirely for cleaner TF-IDF later
        text = ISO_TS.sub("", text, count=1).lstrip()
    else:
        text = text2

    if hostname:
        # Replace hostname token (container id-like host)
        pattern = re.compile(rf"\b{re.escape(hostname)}\b")
        text, n = pattern.subn("<HOST>", text)
        counts["hostnames"] += n

    text, n = PID_BRACKET.subn("sshd[<PID>]", text)
    counts["pids"] += n

    # Username before IP so "user from IP" stays readable
    if username:
        # Replace exact username occurrences (word-ish)
        # Also handle user=NAME and user NAME(uid=)
        patterns = [
            re.compile(rf"\buser={re.escape(username)}\b"),
            re.compile(rf"\binvalid user {re.escape(username)}\b", re.I),
            re.compile(rf"\bfor user {re.escape(username)}\b", re.I),
            re.compile(rf"\bfor {re.escape(username)}\b"),
            re.compile(rf"\buser {re.escape(username)}(?:\(|\b)"),
            re.compile(rf"\bauthenticating user {re.escape(username)}\b", re.I),
            re.compile(rf"\b{re.escape(username)}\(uid=\d+\)"),
            re.compile(rf"\b{re.escape(username)}\b"),
        ]
        for pat in patterns:
            text, n = pat.subn(lambda m: m.group(0).replace(username, "<USER>"), text)
            if n:
                counts["usernames"] += n
                # After first successful family, continue with remaining safer patterns
                # but avoid double-counting heavily — still OK for report totals

    text, n = IPV4.subn("<IP>", text)
    counts["ips"] += n

    text, n = PORT_NUM.subn("port <PORT>", text)
    counts["ports"] += n

    text = WHITESPACE.sub(" ", text).strip()
    if lowercase:
        text = text.lower()
    return text, counts


def merge_counts(dst: dict[str, int], src: dict[str, int]) -> None:
    for k, v in src.items():
        dst[k] = dst.get(k, 0) + v


# Tokens that must survive normalization (sanity helpers for tests)
REQUIRED_SEMANTIC_FRAGMENTS = (
    "failed password",
    "accepted password",
    "authentication failure",
    "session opened",
    "session closed",
)
