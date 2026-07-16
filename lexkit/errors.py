"""
LeXKit Error Taxonomy — v1.0.0
================================
All LeXKit exceptions derive from LexKitError.
Every class carries a stable numeric code for programmatic handling.

Error Codes
-----------
E000  LexKitError          — generic / base
E001  LexKitScanError      — directory scanning / metadata extraction
E002  LexKitCleanError     — document cleaning / encoding repair
E003  LexKitSearchError    — index build or query failure
E004  LexKitDatabaseError  — SQLite read / write failure
E005  LexKitPluginError    — plugin load / register / execute failure
E006  LexKitPipelineError  — pipeline step failure

Usage
-----
    from lexkit.errors import LexKitScanError, wrap

    # Raise a typed error:
    raise LexKitScanError("Cannot read directory", context={"path": str(path)})

    # Wrap stdlib exceptions:
    with wrap(LexKitDatabaseError, context={"table": "files"}):
        conn.execute(...)
"""

from __future__ import annotations

import contextlib
from typing import Any, Generator


class LexKitError(Exception):
    """Base class for all LeXKit exceptions."""

    code: str = "E000"
    default_message: str = "An unexpected LeXKit error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        context: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        self.message  = message or self.default_message
        self.context  = context or {}
        self.cause    = cause
        super().__init__(self.message)

    def __str__(self) -> str:
        base = f"[{self.code}] {self.message}"
        if self.context:
            ctx = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            base = f"{base}  ({ctx})"
        return base

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict (used by the structured logger)."""
        return {
            "error_code": self.code,
            "message":    self.message,
            "context":    self.context,
        }


class LexKitScanError(LexKitError):
    """Raised when directory scanning or metadata extraction fails."""
    code            = "E001"
    default_message = "File scanning failed."


class LexKitCleanError(LexKitError):
    """Raised when document cleaning or encoding repair fails."""
    code            = "E002"
    default_message = "Document cleaning failed."


class LexKitSearchError(LexKitError):
    """Raised when index build or query fails."""
    code            = "E003"
    default_message = "Search operation failed."


class LexKitDatabaseError(LexKitError):
    """Raised when a SQLite operation fails."""
    code            = "E004"
    default_message = "Database operation failed."


class LexKitPluginError(LexKitError):
    """Raised when a plugin cannot be loaded, registered, or executed."""
    code            = "E005"
    default_message = "Plugin error."


class LexKitPipelineError(LexKitError):
    """Raised when a pipeline step fails unrecoverably."""
    code            = "E006"
    default_message = "Pipeline execution failed."


# ── Context manager helper ─────────────────────────────────────────────────────

@contextlib.contextmanager
def wrap(
    exc_class: type[LexKitError],
    message: str | None = None,
    context: dict[str, Any] | None = None,
) -> Generator[None, None, None]:
    """Convert any stdlib exception into a typed LexKitError.

    Example::

        with wrap(LexKitDatabaseError, context={"table": "files"}):
            conn.execute("SELECT * FROM files")
    """
    try:
        yield
    except LexKitError:
        raise  # already typed, pass through unchanged
    except Exception as exc:
        raise exc_class(
            message or str(exc),
            context=context or {},
            cause=exc,
        ) from exc
