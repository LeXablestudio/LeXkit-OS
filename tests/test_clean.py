"""Tests for Document Cleaner."""
from __future__ import annotations
from pathlib import Path
from lexkit.tools.clean import clean_text, _read

class TestCleanText:
    def test_removes_control_chars(self) -> None:
        assert "\x00" not in clean_text("hello\x00world")
    def test_collapses_blank_lines(self) -> None:
        assert "\n\n\n" not in clean_text("a\n\n\n\nb")
    def test_strips(self) -> None:
        assert clean_text("  hello  ") == "hello"
    def test_empty(self) -> None:
        assert clean_text("") == ""
    def test_deterministic(self) -> None:
        t = "text\x00junk   extra\n\n\nlines"
        assert clean_text(t) == clean_text(t)

class TestReadEncoding:
    def test_utf8(self, tmp_path: Path) -> None:
        f = tmp_path/"t.txt"; f.write_text("Hello", encoding="utf-8")
        assert _read(f) == "Hello"
