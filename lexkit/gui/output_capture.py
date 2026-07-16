"""Output capture — redirect LeXKit's rich.Console + stdout to GUI callbacks.

This is the core mechanism that lets the GUI show tool output *live* without
modifying a single tool. LeXKit tools print to a shared ``rich.Console`` instance
(``console = Console()``) and to ``sys.stdout``. We intercept both:

1. **rich.Console**: swap each tool module's ``console`` for one backed by a
   callback-emitting file proxy. Rich renders ANSI markup, so we keep colour.
2. **sys.stdout**: redirect to a buffer polled by a worker, for any plain prints.

On exit, everything is restored so the CLI keeps working normally.

Public API
----------
- :func:`capture_tool_output` — context manager (yields a :class:`OutputTap`).
- :class:`OutputTap`          — holds the live callback + buffered text.
"""

from __future__ import annotations

import io
import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Iterator

#: A callback receiving a chunk of plain/ANSI output text.
OutputCallback = Callable[[str], None]


@dataclass
class OutputTap:
    """A live tap into captured output. Poll ``drain()`` for new text."""

    #: The callback invoked on each captured chunk.
    callback: OutputCallback
    #: Internal buffer for stdout redirection.
    _buffer: io.StringIO = field(default_factory=io.StringIO)
    #: Original rich console objects, saved for restoration.
    _saved_consoles: dict[str, object] = field(default_factory=dict)
    _saved_stdout: object = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _closed: bool = False

    def write_stdout(self, text: str) -> None:
        """Receive a stdout write; buffer it and forward to the callback."""
        if self._closed or not text:
            return
        with self._lock:
            self._buffer.write(text)
        self.callback(text)

    def drain(self) -> str:
        """Return and clear the buffered stdout text (for polling workers)."""
        with self._lock:
            data = self._buffer.getvalue()
            self._buffer.seek(0)
            self._buffer.truncate(0)
        return data

    def emit(self, text: str) -> None:
        """Forward arbitrary text to the callback (e.g. rich rendering)."""
        if not self._closed and text:
            self.callback(text)


class _CallbackStream(io.TextIOBase):
    """A minimal stream that forwards writes to a callback (for rich + stdout)."""

    def __init__(self, callback: OutputCallback) -> None:
        self._callback = callback
        self._buf = io.StringIO()

    def write(self, text: str) -> int:
        if text:
            self._callback(text)
        return len(text)

    def flush(self) -> None:  # noqa: D401
        pass

    def isatty(self) -> bool:
        # Tell rich this is a terminal so it emits ANSI colour codes, which the
        # log panel can render via Qt's ANSI support.
        return True


#: Tool modules whose module-level ``console`` we swap. Kept explicit so capture
#: is deterministic and we never miss a tool.
_TOOL_MODULES = [
    "lexkit.tools.fsm",
    "lexkit.tools.clean",
    "lexkit.tools.batch",
    "lexkit.tools.search",
    "lexkit.tools.refs",
    "lexkit.tools.cite",
    "lexkit.tools.notes",
    "lexkit.tools.split",
    "lexkit.tools.tpl",
    "lexkit.pipelines.runner",
    "lexkit.core.processor",
]


@contextmanager
def capture_tool_output(callback: OutputCallback) -> Iterator[OutputTap]:
    """Context manager that captures all LeXKit tool output for its duration.

    Yields an :class:`OutputTap`. On exit, all redirections are restored.

    Example
    -------
        with capture_tool_output(on_chunk) as tap:
            lexkit.tools.refs.extract(input_path=...)
    """
    tap = OutputTap(callback=callback)
    stream = _CallbackStream(callback)
    rich_console = None

    # 1. Build a rich Console that renders into our callback stream.
    try:
        from rich.console import Console
        rich_console = Console(
            file=stream, color_system="auto", soft_wrap=False, width=100,
            force_terminal=True, highlight=False,
        )
    except Exception:
        rich_console = None

    # 2. Swap module-level consoles.
    import importlib
    saved: dict[str, object] = {}
    for mod_name in _TOOL_MODULES:
        try:
            mod = importlib.import_module(mod_name)
            if hasattr(mod, "console"):
                saved[mod_name] = mod.console
                if rich_console is not None:
                    mod.console = rich_console
        except Exception:
            continue
    tap._saved_consoles = saved

    # 3. Redirect sys.stdout for plain prints.
    tap._saved_stdout = sys.stdout
    sys.stdout = stream  # type: ignore[assignment]

    try:
        yield tap
    finally:
        # Restore everything.
        sys.stdout = tap._saved_stdout  # type: ignore[assignment]
        for mod_name, original in saved.items():
            try:
                mod = importlib.import_module(mod_name)
                mod.console = original
            except Exception:
                pass
        tap._closed = True
