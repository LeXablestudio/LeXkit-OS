"""Tests for the GUI output capture system.

Verifies that LeXKit tool output (rich.Console + stdout) is intercepted by the
capture context manager and forwarded to the callback, without leaking past exit.
"""

import io
import sys

import pytest


def _has_gui_deps() -> bool:
    try:
        import PySide6  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(not _has_gui_deps(), reason="PySide6 not installed")


class TestCapture:
    def test_stdout_redirected(self):
        """Plain prints inside the context go to the callback."""
        from lexkit.gui.output_capture import capture_tool_output
        chunks: list[str] = []
        with capture_tool_output(chunks.append):
            print("hello world")
        joined = "".join(chunks)
        assert "hello world" in joined

    def test_restored_after_exit(self):
        """sys.stdout is restored to the original after the context exits."""
        from lexkit.gui.output_capture import capture_tool_output
        original = sys.stdout
        with capture_tool_output(lambda _t: None):
            assert sys.stdout is not original
        assert sys.stdout is original

    def test_rich_console_captured(self):
        """rich.Console output (the kind tools use) reaches the callback."""
        from lexkit.gui.output_capture import capture_tool_output
        from rich.console import Console
        chunks: list[str] = []
        with capture_tool_output(chunks.append):
            c = Console()
            c.print("[bold red]alert[/bold red] message")
        joined = "".join(chunks)
        assert "alert" in joined

    def test_callback_receives_chunks(self):
        """Multiple writes produce multiple callback invocations."""
        from lexkit.gui.output_capture import capture_tool_output
        count = {"n": 0}

        def cb(_text: str) -> None:
            count["n"] += 1

        with capture_tool_output(cb):
            print("a")
            print("b")
            print("c")
        assert count["n"] >= 3

    def test_no_output_after_exit(self):
        """Writes after the context exits do not reach the callback."""
        from lexkit.gui.output_capture import capture_tool_output
        chunks: list[str] = []
        with capture_tool_output(chunks.append):
            print("inside")
        print("outside")
        joined = "".join(chunks)
        assert "inside" in joined
        assert "outside" not in joined


class TestToolModuleConsoleRestored:
    def test_console_attribute_restored(self):
        """A tool module's `console` is swapped and then restored."""
        from lexkit.gui.output_capture import capture_tool_output
        from lexkit.tools import fsm
        original = fsm.console
        with capture_tool_output(lambda _t: None):
            assert fsm.console is not original  # swapped
        assert fsm.console is original  # restored
