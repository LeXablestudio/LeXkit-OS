"""
LeXKit Structured Logger — v1.0.0
===================================
Emits deterministic, machine-readable JSON-lines logs to:
  - ~/.lexkit/lexkit.log   (always)
  - stderr                 (only when log level <= current level)

Log Record Format
-----------------
{
  "ts":         "2026-06-12T14:30:00.123456Z",   # UTC ISO-8601, deterministic
  "level":      "INFO",
  "tool":       "fsm",
  "event":      "scan_complete",
  "files":      1247,                             # arbitrary context fields
  "error_code": null
}

All timestamps are UTC to guarantee cross-timezone reproducibility.
No calls to datetime.now() with local timezone offset.
No randomness. Same inputs → same log structure.

Usage
-----
    from lexkit.logging import get_logger

    log = get_logger("fsm")
    log.info("scan_complete", files=1247, duration_ms=2100)
    log.error("scan_failed", error_code="E001", path="/data/papers")
    log.warning("duplicate_found", sha256="abc123")
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Log level constants (numeric, lowest = most verbose) ─────────────────────
LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
# Default to WARNING on stderr so routine operations (plugin loading, indexing)
# stay quiet on the console while still being recorded in the log file.
# Use --verbose or configure(level="INFO") to see them.
_DEFAULT_LEVEL = "WARNING"

# ── Singleton log file path ───────────────────────────────────────────────────
_LOG_PATH: Path = Path.home() / ".lexkit" / "lexkit.log"
_CURRENT_LEVEL: int = LEVELS[_DEFAULT_LEVEL]


def configure(log_path: Path | None = None, level: str = "INFO") -> None:
    """Configure global log destination and minimum level."""
    global _LOG_PATH, _CURRENT_LEVEL
    if log_path:
        _LOG_PATH = log_path
    _CURRENT_LEVEL = LEVELS.get(level.upper(), LEVELS["INFO"])


def _now_utc() -> str:
    """Return a deterministic UTC timestamp string in ISO-8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def _emit(record: dict[str, Any]) -> None:
    """Write a single JSON-lines record to the log file and (if level permits) stderr."""
    line = json.dumps(record, separators=(",", ":"), ensure_ascii=False)

    # Always append to file
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass  # Never let logging crash the main process

    # Emit to stderr only at or above the configured level
    numeric = LEVELS.get(record.get("level", "INFO"), 20)
    if numeric >= _CURRENT_LEVEL:
        sys.stderr.write(line + "\n")


class Logger:
    """Per-tool structured logger."""

    def __init__(self, tool: str) -> None:
        self.tool = tool

    def _log(self, level: str, event: str, **fields: Any) -> None:
        record: dict[str, Any] = {
            "ts":    _now_utc(),
            "level": level,
            "tool":  self.tool,
            "event": event,
        }
        record.update(fields)
        _emit(record)

    def debug(self, event: str, **fields: Any) -> None:
        self._log("DEBUG", event, **fields)

    def info(self, event: str, **fields: Any) -> None:
        self._log("INFO", event, **fields)

    def warning(self, event: str, **fields: Any) -> None:
        self._log("WARNING", event, **fields)

    def error(self, event: str, **fields: Any) -> None:
        self._log("ERROR", event, **fields)

    def critical(self, event: str, **fields: Any) -> None:
        self._log("CRITICAL", event, **fields)

    def exception(self, event: str, exc: BaseException, **fields: Any) -> None:
        """Log an exception with its type and message."""
        from lexkit.errors import LexKitError
        extra: dict[str, Any] = {
            "exc_type": type(exc).__name__,
            "exc_msg":  str(exc),
        }
        if isinstance(exc, LexKitError):
            extra["error_code"] = exc.code
            extra.update(exc.context)
        extra.update(fields)
        self._log("ERROR", event, **extra)


def get_logger(tool: str) -> Logger:
    """Return a Logger instance for the given tool name."""
    return Logger(tool)
