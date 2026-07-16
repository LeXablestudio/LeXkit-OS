"""Extended tests for the output capture system — OutputTap, _CallbackStream, edge cases."""

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


class TestOutputTap:
    def test_write_stdout_forwards_to_callback(self):
        from lexkit.gui.output_capture import OutputTap
        chunks = []
        tap = OutputTap(callback=chunks.append)
        tap.write_stdout("hello")
        assert "hello" in chunks

    def test_write_stdout_buffers(self):
        from lexkit.gui.output_capture import OutputTap
        tap = OutputTap(callback=lambda _t: None)
        tap.write_stdout("aaa")
        tap.write_stdout("bbb")
        data = tap.drain()
        assert "aaa" in data
        assert "bbb" in data

    def test_drain_clears_buffer(self):
        from lexkit.gui.output_capture import OutputTap
        tap = OutputTap(callback=lambda _t: None)
        tap.write_stdout("once")
        tap.drain()
        data = tap.drain()
        assert data == ""

    def test_write_stdout_ignores_empty(self):
        from lexkit.gui.output_capture import OutputTap
        chunks = []
        tap = OutputTap(callback=chunks.append)
        tap.write_stdout("")
        assert len(chunks) == 0

    def test_emit_forwards_to_callback(self):
        from lexkit.gui.output_capture import OutputTap
        chunks = []
        tap = OutputTap(callback=chunks.append)
        tap.emit("test123")
        assert "test123" in chunks

    def test_emit_ignores_empty(self):
        from lexkit.gui.output_capture import OutputTap
        chunks = []
        tap = OutputTap(callback=chunks.append)
        tap.emit("")
        assert len(chunks) == 0

    def test_write_stdout_after_close_ignored(self):
        from lexkit.gui.output_capture import OutputTap
        chunks = []
        tap = OutputTap(callback=chunks.append)
        tap._closed = True
        tap.write_stdout("should not appear")
        assert len(chunks) == 0

    def test_emit_after_close_ignored(self):
        from lexkit.gui.output_capture import OutputTap
        chunks = []
        tap = OutputTap(callback=chunks.append)
        tap._closed = True
        tap.emit("should not appear")
        assert len(chunks) == 0


class TestCallbackStream:
    def test_write_forwards(self):
        from lexkit.gui.output_capture import _CallbackStream
        chunks = []
        stream = _CallbackStream(chunks.append)
        stream.write("abc")
        assert "abc" in chunks

    def test_write_returns_length(self):
        from lexkit.gui.output_capture import _CallbackStream
        stream = _CallbackStream(lambda _t: None)
        n = stream.write("hello")
        assert n == 5

    def test_flush_noop(self):
        from lexkit.gui.output_capture import _CallbackStream
        stream = _CallbackStream(lambda _t: None)
        stream.flush()  # should not raise

    def test_isatty_returns_true(self):
        from lexkit.gui.output_capture import _CallbackStream
        stream = _CallbackStream(lambda _t: None)
        assert stream.isatty() is True

    def test_empty_write(self):
        from lexkit.gui.output_capture import _CallbackStream
        chunks = []
        stream = _CallbackStream(chunks.append)
        stream.write("")
        assert len(chunks) == 0


class TestCaptureToolOutputExtended:
    def test_concurrent_prints(self):
        from lexkit.gui.output_capture import capture_tool_output
        chunks = []
        with capture_tool_output(chunks.append):
            for i in range(50):
                print(f"line-{i}")
        joined = "".join(chunks)
        assert "line-0" in joined
        assert "line-49" in joined

    def test_rich_render_styled(self):
        from lexkit.gui.output_capture import capture_tool_output
        from rich.console import Console
        chunks = []
        with capture_tool_output(chunks.append):
            c = Console(force_terminal=True, width=80)
            c.print("[green]success[/green]")
        joined = "".join(chunks)
        assert "success" in joined

    def test_nested_context_not_allowed(self):
        """Second capture_tool_output restores stdout from the first on exit."""
        from lexkit.gui.output_capture import capture_tool_output
        original = sys.stdout
        chunks1 = []
        chunks2 = []
        with capture_tool_output(chunks1.append):
            print("outer")
            with capture_tool_output(chunks2.append):
                print("inner")
            # After inner exits, outer's stdout should be restored.
            print("after-inner")
        assert "outer" in "".join(chunks1)
        assert "inner" in "".join(chunks2)
        assert sys.stdout is original

    def test_exception_inside_captures_output(self):
        from lexkit.gui.output_capture import capture_tool_output
        chunks = []
        try:
            with capture_tool_output(chunks.append):
                print("before-error")
                raise ValueError("test")
        except ValueError:
            pass
        joined = "".join(chunks)
        assert "before-error" in joined

    def test_all_tool_modules_restored(self):
        """Every tool module's console is restored after capture exits."""
        from lexkit.gui.output_capture import capture_tool_output, _TOOL_MODULES
        import importlib

        originals = {}
        for mod_name in _TOOL_MODULES:
            try:
                mod = importlib.import_module(mod_name)
                if hasattr(mod, "console"):
                    originals[mod_name] = mod.console
            except Exception:
                pass

        with capture_tool_output(lambda _t: None):
            pass

        for mod_name, original in originals.items():
            mod = importlib.import_module(mod_name)
            assert mod.console is original, f"{mod_name}.console not restored"
