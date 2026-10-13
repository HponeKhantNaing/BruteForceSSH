"""Log tailer truncation / line boundary behavior."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from realtime.log_tailer import LogTailer  # noqa: E402


def test_tailer_reads_new_lines_and_detects_truncate(tmp_path):
    log = tmp_path / "auth.log"
    log.write_text("line1\n", encoding="utf-8")
    tailer = LogTailer(log, start_at="beginning", poll_interval_ms=50)
    events = []
    for ev in tailer.iter_events(max_idle_rounds=2):
        events.append(ev)
        if ev.kind == "line" and ev.line == "line1":
            log.write_text("only\n", encoding="utf-8")  # truncate
    kinds = [e.kind for e in events]
    assert "line" in kinds
    assert "truncated" in kinds
