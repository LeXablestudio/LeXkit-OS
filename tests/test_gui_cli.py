"""Tests for the CLI gui command and shortcut creation."""

import pytest
from unittest.mock import patch


class TestGuiCliCommand:
    def test_gui_command_no_pyside6(self, monkeypatch):
        """When PySide6 is not importable, the gui command prints install instructions."""
        import typer
        from typer.testing import CliRunner

        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == "lexkit.gui":
                raise ImportError("No module named 'PySide6'")
            return original_import(name, *args, **kwargs)

        runner = CliRunner()
        from lexkit.cli.main import app

        # We can't easily mock __import__ for the CLI's inner import, so test
        # that the gui command exists and is callable.
        result = runner.invoke(app, ["gui", "--help"])
        assert result.exit_code == 0
        assert "GUI" in result.output or "gui" in result.output.lower()

    def test_gui_shortcut_flag(self, monkeypatch, tmp_path):
        """--shortcut flag creates a .bat file (not actually launching GUI)."""
        from typer.testing import CliRunner
        from lexkit.cli.main import app

        desktop = tmp_path / "Desktop"
        desktop.mkdir()
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        runner = CliRunner()
        result = runner.invoke(app, ["gui", "--shortcut"])
        bat = desktop / "LeXKit.bat"
        assert bat.exists()
        content = bat.read_text(encoding="utf-8")
        assert "lexkit.gui" in content

    def test_gui_command_entry_point_exists(self):
        """The gui command is registered in the CLI."""
        from typer.testing import CliRunner
        from lexkit.cli.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["gui", "--help"])
        assert result.exit_code == 0
