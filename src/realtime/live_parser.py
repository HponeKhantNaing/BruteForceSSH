"""Live auth-line parsing using P6 parser + P4 role patterns."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from labeling.p4_labeling import annotate_line
from preprocessing.auth_parser import parse_auth_line


class LiveParser:
    def __init__(self, policy_path: Path):
        policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
        self.patterns = list((policy.get("event_roles") or {}).get("patterns") or [])
        self.line_number = 0
        self.unclassified = 0

    def parse_line(self, raw_line: str) -> dict[str, Any] | None:
        """Return a stream event dict, or None if blank."""
        if not raw_line.strip():
            return None
        self.line_number += 1
        parsed = parse_auth_line(raw_line)
        role, rule, status = annotate_line(raw_line, self.patterns)
        if role == "UNCLASSIFIED":
            self.unclassified += 1
        return {
            "event_id": f"LIVE:{self.line_number:08d}",
            "line_number": self.line_number,
            "event_role": role,
            "parser_rule": rule,
            "parse_status": status,
            "timestamp_iso": parsed.get("timestamp_iso"),
            "timestamp_raw": parsed.get("timestamp_raw"),
            "pid": parsed.get("pid"),
            "process": parsed.get("process"),
            "source_ip": parsed.get("source_ip"),
            "username_raw": parsed.get("username_raw"),
            "raw_line": raw_line,
            "message": parsed.get("message"),
        }
