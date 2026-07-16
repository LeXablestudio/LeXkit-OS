"""Tests for the plugin system."""

from __future__ import annotations

import pytest
import typer

from lexkit.plugins.base     import PluginBase, TyperPlugin
from lexkit.plugins.registry import PluginRegistry
from lexkit.errors           import LexKitPluginError


# ── Fixture helpers ───────────────────────────────────────────────────────────

def make_plugin(name: str, version: str = "1.0.0") -> PluginBase:
    """Create a minimal concrete plugin for testing."""
    _app = typer.Typer(name=name)
    return TyperPlugin(name=name, typer_app=_app, description=f"Test plugin {name}", version=version)


# ── PluginBase ────────────────────────────────────────────────────────────────

class TestPluginBase:
    def test_repr(self) -> None:
        p = make_plugin("ocr", "0.2.0")
        assert "ocr" in repr(p)
        assert "0.2.0" in repr(p)

    def test_abstract_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            PluginBase()  # type: ignore[abstract]


# ── PluginRegistry ────────────────────────────────────────────────────────────

class TestPluginRegistry:
    def _fresh(self) -> PluginRegistry:
        return PluginRegistry()

    def test_register_and_retrieve(self) -> None:
        reg = self._fresh()
        p   = make_plugin("fsm")
        reg.register(p)
        assert reg.get("fsm") is p

    def test_duplicate_raises(self) -> None:
        reg = self._fresh()
        reg.register(make_plugin("dup"))
        with pytest.raises(LexKitPluginError):
            reg.register(make_plugin("dup"))

    def test_no_name_raises(self) -> None:
        reg    = self._fresh()
        bad    = make_plugin("temp")
        bad.name = ""
        with pytest.raises(LexKitPluginError):
            reg.register(bad)

    def test_non_plugin_raises(self) -> None:
        reg = self._fresh()
        with pytest.raises(LexKitPluginError):
            reg.register("not a plugin")  # type: ignore[arg-type]

    def test_all_sorted(self) -> None:
        reg = self._fresh()
        for name in ["zap", "alpha", "middle"]:
            reg.register(make_plugin(name))
        names = [p.name for p in reg.all()]
        assert names == sorted(names)

    def test_contains(self) -> None:
        reg = self._fresh()
        reg.register(make_plugin("search"))
        assert "search" in reg
        assert "missing" not in reg

    def test_len(self) -> None:
        reg = self._fresh()
        for i in range(4):
            reg.register(make_plugin(f"tool_{i}"))
        assert len(reg) == 4

    def test_iter(self) -> None:
        reg = self._fresh()
        reg.register(make_plugin("a"))
        reg.register(make_plugin("b"))
        names = [p.name for p in reg]
        assert "a" in names and "b" in names
