"""Tests for Template Generator."""
from lexkit.tools.tpl import _render, TEMPLATES

class TestTemplates:
    def test_all_formats(self) -> None:
        for f in ["apa","ieee","acm"]: assert f in TEMPLATES

    def test_apa_has_title(self) -> None:
        assert "UniqueTitle" in _render("apa","UniqueTitle","Author")

    def test_ieee_has_author(self) -> None:
        assert "JSmith" in _render("ieee","Title","JSmith")

    def test_acm_renders(self) -> None:
        assert "acmart" in _render("acm","Title","Author")

    def test_deterministic(self) -> None:
        assert _render("apa","T","A") == _render("apa","T","A")
