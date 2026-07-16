"""LeXKit Desktop GUI — a PySide6 dashboard for the entire toolkit.

Run with::
    python -m lexkit.gui
    lexkit-gui
    lexkit gui

The GUI drives the same deterministic LeXKit functions as the CLI; no tool logic
is duplicated or modified. Tool output is captured live via
:mod:`lexkit.gui.output_capture` and streamed to the log panel.
"""

from lexkit.gui.app import main

__all__ = ["main"]
