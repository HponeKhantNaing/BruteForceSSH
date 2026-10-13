"""Follow an appending log file with truncation / replacement detection."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator


@dataclass
class TailEvent:
    kind: str  # line | truncated | replaced | missing | rotated
    line: str | None = None
    detail: str | None = None


class LogTailer:
    """Byte-offset tailer that preserves line boundaries."""

    def __init__(
        self,
        path: Path,
        *,
        start_at: str = "end",
        poll_interval_ms: int = 200,
    ):
        self.path = path
        self.start_at = start_at
        self.poll_interval = max(poll_interval_ms, 50) / 1000.0
        self._offset = 0
        self._inode: int | None = None
        self._buffer = ""
        self._initialized = False

    def _stat(self) -> os.stat_result | None:
        try:
            return self.path.stat()
        except FileNotFoundError:
            return None

    def _open_position(self) -> None:
        st = self._stat()
        if st is None:
            self._inode = None
            self._offset = 0
            return
        self._inode = st.st_ino
        if self.start_at == "end" and not self._initialized:
            self._offset = st.st_size
        elif self.start_at == "beginning":
            self._offset = 0
        self._initialized = True

    def iter_events(
        self,
        *,
        max_idle_rounds: int | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> Iterator[TailEvent]:
        """Yield TailEvents. Stops when should_stop() is true or idle rounds exhausted."""
        idle = 0
        if not self._initialized:
            self._open_position()
        while True:
            if should_stop is not None and should_stop():
                return
            st = self._stat()
            if st is None:
                yield TailEvent(kind="missing", detail="log file not found")
                idle += 1
                if max_idle_rounds is not None and idle >= max_idle_rounds:
                    return
                time.sleep(self.poll_interval)
                continue

            if self._inode is not None and st.st_ino != self._inode:
                yield TailEvent(kind="replaced", detail="inode changed")
                self._inode = st.st_ino
                self._offset = 0
                self._buffer = ""

            if st.st_size < self._offset:
                yield TailEvent(kind="truncated", detail="file size shrank")
                self._offset = 0
                self._buffer = ""

            if st.st_size == self._offset and not self._buffer:
                # Heartbeat so callers can run idle/timeout logic without new lines.
                yield TailEvent(kind="idle")
                idle += 1
                if max_idle_rounds is not None and idle >= max_idle_rounds:
                    return
                time.sleep(self.poll_interval)
                continue

            idle = 0
            with self.path.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(self._offset)
                chunk = f.read()
                self._offset = f.tell()
            if not chunk:
                time.sleep(self.poll_interval)
                continue
            self._buffer += chunk
            while "\n" in self._buffer:
                if should_stop is not None and should_stop():
                    return
                line, self._buffer = self._buffer.split("\n", 1)
                yield TailEvent(kind="line", line=line)

    def read_existing_lines(self) -> list[str]:
        """Read entire current file as complete lines (replay helper)."""
        if not self.path.is_file():
            return []
        text = self.path.read_text(encoding="utf-8", errors="replace")
        return [ln for ln in text.splitlines()]
