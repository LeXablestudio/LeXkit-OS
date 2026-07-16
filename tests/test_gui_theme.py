"""Tests for the LeXKit dark theme and LogPanel widget."""

import pytest


def _has_gui_deps() -> bool:
    try:
        import PySide6  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(not _has_gui_deps(), reason="PySide6 not installed")


class TestTheme:
    def test_colors_dict_complete(self):
        from lexkit.gui.theme import COLORS
        required_keys = {
            "bg", "bg_alt", "surface", "border", "magenta", "magenta_lt",
            "cyan", "green", "yellow", "red", "text", "text_dim",
        }
        assert required_keys.issubset(COLORS.keys())

    def test_all_colors_are_hex(self):
        from lexkit.gui.theme import COLORS
        import re
        hex_re = re.compile(r"^#[0-9a-fA-F]{6}$")
        for name, color in COLORS.items():
            assert hex_re.match(color), f"COLORS[{name!r}] = {color!r} is not a hex color"

    def test_qss_not_empty(self):
        from lexkit.gui.theme import QSS
        assert len(QSS) > 500
        assert "QWidget" in QSS
        assert "QPushButton" in QSS

    def test_apply_theme(self, monkeypatch):
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from lexkit.gui.theme import apply_theme

        app = QApplication.instance() or QApplication([])
        apply_theme(app)
        assert len(app.styleSheet()) > 0

    def test_brand_color_in_qss(self):
        from lexkit.gui.theme import QSS, COLORS
        assert COLORS["magenta"] in QSS
        assert COLORS["bg"] in QSS


class TestLogPanel:
    def test_constructs(self, monkeypatch):
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from lexkit.gui.widgets.log_panel import LogPanel

        app = QApplication.instance() or QApplication([])
        lp = LogPanel("Test")
        assert lp is not None

    def test_append_adds_text(self, monkeypatch):
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from lexkit.gui.widgets.log_panel import LogPanel

        app = QApplication.instance() or QApplication([])
        lp = LogPanel("Test")
        lp.append("hello world")
        text = lp._edit.toPlainText()
        assert "hello world" in text

    def test_append_line(self, monkeypatch):
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from lexkit.gui.widgets.log_panel import LogPanel

        app = QApplication.instance() or QApplication([])
        lp = LogPanel("Test")
        lp.append_line("line one")
        text = lp._edit.toPlainText()
        assert "line one" in text

    def test_empty_string_no_crash(self, monkeypatch):
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from lexkit.gui.widgets.log_panel import LogPanel

        app = QApplication.instance() or QApplication([])
        lp = LogPanel("Test")
        lp.append("")
        lp.append_line("")

    def test_clear(self, monkeypatch):
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from lexkit.gui.widgets.log_panel import LogPanel

        app = QApplication.instance() or QApplication([])
        lp = LogPanel("Test")
        lp.append("some text")
        assert len(lp._edit.toPlainText()) > 0
        lp.clear()
        assert len(lp._edit.toPlainText()) == 0

    def test_ansi_to_html_bold(self):
        from lexkit.gui.widgets.log_panel import ansi_to_html
        html = ansi_to_html("\x1b[1mbold\x1b[0m")
        assert "bold" in html

    def test_ansi_to_html_multiple_colors(self):
        from lexkit.gui.widgets.log_panel import ansi_to_html
        html = ansi_to_html("\x1b[31mred\x1b[0m normal \x1b[32mgreen\x1b[0m")
        assert "red" in html
        assert "green" in html
        assert "normal" in html

    def test_ansi_to_html_ampersand_escaped(self):
        from lexkit.gui.widgets.log_panel import ansi_to_html
        html = ansi_to_html("a & b")
        assert "&amp;" in html
        assert "a & b" not in html

    def test_ansi_to_html_newline_to_br(self):
        from lexkit.gui.widgets.log_panel import ansi_to_html
        html = ansi_to_html("line1\nline2")
        assert "<br>" in html
        assert "line1" in html
        assert "line2" in html
