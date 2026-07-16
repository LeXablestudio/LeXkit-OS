"""Smoke tests for the main GUI window and worker threads.

Qt widget tests run headlessly via the ``offscreen`` QPA platform. These verify
that the whole app constructs, panels wire up, and the worker thread can run a
tool without blocking — without requiring a display.
"""

import os

import pytest


def _has_gui_deps() -> bool:
    try:
        import PySide6  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(not _has_gui_deps(), reason="PySide6 not installed")


@pytest.fixture(scope="module")
def qapp():
    """A shared headless QApplication for the module."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class TestMainWindow:
    def test_constructs(self, qapp):
        from lexkit.gui.app import MainWindow
        w = MainWindow()
        assert w.windowTitle().startswith("LeXKit v")

    def test_all_panels_present(self, qapp):
        from lexkit.gui.app import MainWindow
        w = MainWindow()
        # 1 dashboard + 9 tools + 4 result viewers = 14
        assert w._stack.count() == 14

    def test_navigation_switches(self, qapp):
        from lexkit.gui.app import MainWindow
        w = MainWindow()
        for i in range(w._stack.count()):
            w._switch_to(i)
            assert w._stack.currentIndex() == i

    def test_refresh_results_no_crash(self, qapp):
        from lexkit.gui.app import MainWindow
        w = MainWindow()
        # Should not raise even with an empty/missing DB.
        w._refresh_results()


class TestToolWorker:
    def test_runs_function_and_emits(self, qapp):
        """Worker runs a plain function and emits finished_ok."""
        from PySide6.QtCore import QTimer
        from lexkit.gui.workers import ToolWorker

        results = {"done": False, "value": None, "log": []}

        def task():
            print("working")
            return 42

        w = ToolWorker(task)
        w.log_line.connect(results["log"].append)
        w.finished_ok.connect(lambda r: results.update(done=True, value=r))

        w.start()
        # Process events until the worker finishes (timeout after 5s).
        for _ in range(500):
            qapp.processEvents()
            if results["done"]:
                break
            w.wait(10)
        assert results["done"] is True
        assert results["value"] == 42
        assert any("working" in c for c in results["log"])

    def test_failure_emits_error(self, qapp):
        """A failing function emits the failed signal."""
        from lexkit.gui.workers import ToolWorker

        results = {"failed": None}

        def bad_task():
            raise ValueError("boom")

        w = ToolWorker(bad_task)
        w.failed.connect(lambda msg: results.update(failed=msg))
        w.start()
        for _ in range(500):
            qapp.processEvents()
            if results["failed"]:
                break
            w.wait(10)
        assert results["failed"] is not None
        assert "boom" in results["failed"]


class TestAnsiConversion:
    def test_plain_passthrough(self):
        from lexkit.gui.widgets.log_panel import ansi_to_html
        assert "hello" in ansi_to_html("hello")

    def test_color_codes_translated(self):
        from lexkit.gui.widgets.log_panel import ansi_to_html
        html = ansi_to_html("\x1b[31mred text\x1b[0m")
        assert "red text" in html
        assert "span" in html  # color wrapping applied

    def test_control_stripped(self):
        from lexkit.gui.widgets.log_panel import ansi_to_html
        # OSC / cursor sequences removed, no leftover escape chars.
        html = ansi_to_html("a\x1b]0;title\x07b\x1b[2Kc")
        assert "\x1b" not in html
        assert "abc" in html.replace("<br>", "")

    def test_html_escaped(self):
        from lexkit.gui.widgets.log_panel import ansi_to_html
        html = ansi_to_html("<script>")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
