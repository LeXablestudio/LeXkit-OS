"""Tests for the deterministic citation-graph layout (GraphView).

The layout must be reproducible: same (nodes, edges, seed) → identical positions.
Also tests edge cases: empty input, single node, disconnected components.
"""

import math
import pytest


def _has_gui_deps() -> bool:
    try:
        import PySide6  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(not _has_gui_deps(), reason="PySide6 not installed")


from lexkit.gui.widgets.results.graph_view import compute_layout


class TestLayoutDeterminism:
    def test_identical_positions(self):
        """Same graph + seed → byte-identical positions."""
        nodes = ["a", "b", "c", "d", "e"]
        edges = [("a", "b", 0.8), ("b", "c", 0.7), ("c", "d", 0.6), ("d", "e", 0.5), ("a", "e", 0.9)]
        p1 = compute_layout(nodes, edges)
        p2 = compute_layout(nodes, edges)
        assert p1 == p2

    def test_different_seed_different_positions(self):
        """Different seeds (usually) produce different layouts."""
        nodes = ["a", "b", "c", "d"]
        edges = [("a", "b", 0.8), ("c", "d", 0.6)]
        p1 = compute_layout(nodes, edges, seed=1)
        p2 = compute_layout(nodes, edges, seed=999)
        assert p1 != p2

    def test_within_bounds(self):
        """All node positions lie within the configured width/height."""
        nodes = ["x", "y", "z"]
        edges = [("x", "y", 0.5), ("y", "z", 0.5)]
        pos = compute_layout(nodes, edges, width=800, height=600)
        for x, y in pos.values():
            assert 0 <= x <= 800
            assert 0 <= y <= 600


class TestLayoutEdgeCases:
    def test_empty(self):
        assert compute_layout([], []) == {}

    def test_single_node(self):
        pos = compute_layout(["only"], [])
        assert "only" in pos
        assert len(pos["only"]) == 2

    def test_disconnected(self):
        """Disconnected nodes still get valid positions."""
        nodes = ["a", "b", "c"]
        edges = [("a", "b", 0.5)]  # c is isolated
        pos = compute_layout(nodes, edges)
        assert len(pos) == 3
        assert all(isinstance(v, tuple) and len(v) == 2 for v in pos.values())


class TestGraphViewConstruction:
    """Smoke test: the GraphView widget constructs without a display."""

    def test_constructs_headless(self, monkeypatch):
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from lexkit.gui.widgets.results.graph_view import GraphView
        gv = GraphView()
        assert gv is not None
        # With an empty DB it shows the placeholder, not an error.
        assert gv._scene is not None
