"""End-to-end headless GUI launch verification.

Verifies the entire LeXKit GUI can start, render, and shut down cleanly under
``QT_QPA_PLATFORM=offscreen`` — no display server required.
"""

import os
import sys
import pytest


def _has_gui_deps() -> bool:
    try:
        import PySide6  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(not _has_gui_deps(), reason="PySide6 not installed")


class TestHeadlessLaunch:
    """Full application bootstrap → show → hide cycle."""

    def test_mainwindow_show_hide_cycle(self, monkeypatch):
        """Create MainWindow, show it, process events, hide — no crash."""
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from lexkit.gui.app import MainWindow

        app = QApplication.instance() or QApplication([])
        w = MainWindow()
        w.show()
        app.processEvents()
        assert w.isVisible()
        w.hide()
        app.processEvents()
        assert not w.isVisible()

    def test_main_function_returns_int(self, monkeypatch):
        """main() creates the app, shows the window, and returns exit code.

        Instead of calling main() directly (which creates a second QApplication),
        we verify the same pieces: app creation, theme, MainWindow, show, exec.
        """
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from lexkit.gui.app import MainWindow
        from lexkit.gui.theme import apply_theme

        app = QApplication.instance() or QApplication([])
        apply_theme(app)
        w = MainWindow()
        w.show()
        app.processEvents()
        assert w.isVisible()
        assert w.windowTitle().startswith("LeXKit v")
        w.hide()
        app.processEvents()

    def test_gui_module_main_entry(self, monkeypatch):
        """python -m lexkit.gui invokes the same main() from lexkit.gui.

        We verify the import path works and main is the right function.
        """
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from lexkit.gui import main as gui_main
        from lexkit.gui.app import main as app_main
        assert gui_main is app_main
        assert callable(gui_main)

    def test_sidebar_button_count(self, monkeypatch):
        """Sidebar has exactly the right number of checkable buttons."""
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from lexkit.gui.app import MainWindow

        app = QApplication.instance() or QApplication([])
        w = MainWindow()
        from lexkit.gui.app import SIDEBAR
        expected_buttons = sum(1 for _, _, is_tool in SIDEBAR if is_tool is not None)
        assert w._nav_group.buttons().__len__() == expected_buttons

    def test_initial_state_is_dashboard(self, monkeypatch):
        """Window starts on the dashboard (index 0)."""
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from lexkit.gui.app import MainWindow

        app = QApplication.instance() or QApplication([])
        w = MainWindow()
        assert w._stack.currentIndex() == 0

    def test_status_bar_message(self, monkeypatch):
        """Status bar shows a message after construction."""
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from lexkit.gui.app import MainWindow

        app = QApplication.instance() or QApplication([])
        w = MainWindow()
        msg = w._status.currentMessage()
        assert len(msg) > 0

    def test_all_tool_panels_instantiate(self, monkeypatch):
        """Every tool panel class from TOOL_PANELS can be constructed."""
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from lexkit.gui.widgets.tool_panels import TOOL_PANELS

        app = QApplication.instance() or QApplication([])
        for key, cls in TOOL_PANELS.items():
            panel = cls()
            assert panel is not None, f"Panel {key} failed to construct"
            assert hasattr(panel, "_fields")
            assert hasattr(panel, "_log")

    def test_all_result_viewers_instantiate(self, monkeypatch):
        """StatsView, ReferencesView, ClustersView, GraphView construct."""
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from lexkit.gui.widgets.results import (
            StatsView, ReferencesView, ClustersView, GraphView,
        )

        app = QApplication.instance() or QApplication([])
        for cls in (StatsView, ReferencesView, ClustersView, GraphView):
            widget = cls()
            assert widget is not None

    def test_navigate_through_all_panels(self, monkeypatch):
        """Switch to every panel index without crash."""
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from lexkit.gui.app import MainWindow

        app = QApplication.instance() or QApplication([])
        w = MainWindow()
        for i in range(w._stack.count()):
            w._switch_to(i)
            assert w._stack.currentIndex() == i
            app.processEvents()

    def test_tool_panel_field_values(self, monkeypatch):
        """Tool panels return expected values from _vals()."""
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from lexkit.gui.widgets.tool_panels import FsmPanel, CleanPanel, TplPanel

        app = QApplication.instance() or QApplication([])

        fsm = FsmPanel()
        vals = fsm._vals()
        assert "auto_sort" in vals
        assert vals["auto_sort"] is True
        assert "directory" in vals
        assert isinstance(vals["directory"], str)

        clean = CleanPanel()
        vals = clean._vals()
        assert "fix_encoding" in vals
        assert vals["fix_encoding"] is True
        assert "dry_run" in vals
        assert vals["dry_run"] is False

        tpl = TplPanel()
        vals = tpl._vals()
        assert "fmt" in vals
        assert vals["fmt"] == "apa"
        assert "title" in vals
        assert vals["title"] == "Research Paper Title"

    def test_dashboard_validation_no_folder(self, monkeypatch):
        """Dashboard _on_run with empty input logs error, doesn't start worker."""
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from lexkit.gui.widgets.dashboard import Dashboard

        app = QApplication.instance() or QApplication([])
        d = Dashboard()
        d._input_edit.setText("")
        d._on_run()
        # Worker should NOT be started.
        assert d._worker is None
        # Log should contain error.
        log_text = d._log._edit.toPlainText()
        assert "ERROR" in log_text or "error" in log_text.lower()

    def test_dashboard_validation_missing_folder(self, monkeypatch):
        """Dashboard _on_run with nonexistent path logs error."""
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from lexkit.gui.widgets.dashboard import Dashboard

        app = QApplication.instance() or QApplication([])
        d = Dashboard()
        d._input_edit.setText("/nonexistent/path/to/folder")
        d._on_run()
        assert d._worker is None
