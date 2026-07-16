"""Background workers — run LeXKit tools in QThreads without blocking the UI.

The GUI never calls a tool directly on the main thread; it spawns a
:class:`ToolWorker` (a ``QThread`` subclass) that runs the callable under
:func:`output_capture.capture_tool_output` and streams the result back via Qt
signals.

Signals
-------
- ``started``    — work has begun.
- ``log_line``   — a chunk of captured output (ANSI).
- ``finished_ok(result)``  — succeeded, returns the callable's return value.
- ``failed(error_text)``   — raised an exception.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QThread, Signal

from lexkit.gui.output_capture import capture_tool_output


class ToolWorker(QThread):
    """Run a single callable in the background, capturing its output."""

    started_signal = Signal()
    log_line = Signal(str)
    finished_ok = Signal(object)   # the return value (may be None)
    failed = Signal(str)           # error message

    def __init__(
        self,
        func: Callable[..., Any],
        args: tuple = (),
        kwargs: dict | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._func = func
        self._args = args
        self._kwargs = kwargs or {}
        self._result: Any = None

    def run(self) -> None:  # noqa: D401 — QThread entry point
        self.started_signal.emit()
        try:
            with capture_tool_output(self.log_line.emit):
                self._result = self._func(*self._args, **self._kwargs)
            self.finished_ok.emit(self._result)
        except Exception as exc:  # noqa: BLE001 — surface every failure to the UI
            self.log_line.emit(f"\n[ERROR] {type(exc).__name__}: {exc}\n")
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    @property
    def result(self) -> Any:
        return self._result


def run_in_worker(
    func: Callable[..., Any],
    *args: Any,
    on_log: Callable[[str], None] | None = None,
    on_done: Callable[[Any], None] | None = None,
    on_fail: Callable[[str], None] | None = None,
    **kwargs: Any,
) -> ToolWorker:
    """Convenience: create, wire signals, and start a ToolWorker. Returns it."""
    worker = ToolWorker(func, args, kwargs)
    if on_log:
        worker.log_line.connect(on_log)
    if on_done:
        worker.finished_ok.connect(on_done)
    if on_fail:
        worker.failed.connect(on_fail)
    worker.start()
    return worker
