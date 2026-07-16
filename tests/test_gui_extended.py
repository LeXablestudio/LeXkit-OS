"""Extended tests for graph view layout + table view widgets."""

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
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class TestComputeLayoutExtended:
    def test_all_nodes_present_in_result(self):
        from lexkit.gui.widgets.results.graph_view import compute_layout
        nodes = ["a", "b", "c", "d", "e", "f"]
        edges = [("a", "b", 0.9), ("c", "d", 0.5), ("e", "f", 0.3)]
        pos = compute_layout(nodes, edges)
        assert set(pos.keys()) == set(nodes)

    def test_no_edges_layout_runs(self):
        from lexkit.gui.widgets.results.graph_view import compute_layout
        nodes = ["a", "b", "c"]
        pos = compute_layout(nodes, [], iterations=100)
        assert len(pos) == 3
        for x, y in pos.values():
            assert isinstance(x, (int, float))
            assert isinstance(y, (int, float))

    def test_custom_dimensions(self):
        from lexkit.gui.widgets.results.graph_view import compute_layout
        nodes = ["a", "b"]
        edges = [("a", "b", 1.0)]
        pos = compute_layout(nodes, edges, width=200, height=100)
        for x, y in pos.values():
            assert 0 <= x <= 200
            assert 0 <= y <= 100

    def test_many_nodes(self):
        from lexkit.gui.widgets.results.graph_view import compute_layout
        nodes = [f"node_{i}" for i in range(50)]
        edges = [(f"node_{i}", f"node_{i+1}", 0.5) for i in range(49)]
        pos = compute_layout(nodes, edges)
        assert len(pos) == 50

    def test_iteration_count_affects_layout(self):
        from lexkit.gui.widgets.results.graph_view import compute_layout
        nodes = ["a", "b", "c", "d"]
        edges = [("a", "b", 0.8), ("b", "c", 0.7), ("c", "d", 0.6)]
        p1 = compute_layout(nodes, edges, iterations=10)
        p2 = compute_layout(nodes, edges, iterations=500)
        # More iterations generally produce a different (better) layout.
        # They could theoretically be equal but it's extremely unlikely.
        assert p1 != p2

    def test_large_score_range(self):
        from lexkit.gui.widgets.results.graph_view import compute_layout
        nodes = ["a", "b", "c"]
        edges = [("a", "b", 0.01), ("b", "c", 0.99)]
        pos = compute_layout(nodes, edges)
        assert len(pos) == 3


class TestGraphViewExtended:
    def test_load_edges_empty_db(self, qapp):
        from lexkit.gui.widgets.results.graph_view import GraphView
        gv = GraphView()
        edges = gv.load_edges()
        assert isinstance(edges, list)

    def test_refresh_with_no_data(self, qapp):
        from lexkit.gui.widgets.results.graph_view import GraphView
        gv = GraphView()
        gv.refresh()
        assert gv._scene is not None
        # Should show placeholder text.
        assert len(gv._node_items) == 0

    def test_focus_node_unknown_key(self, qapp):
        from lexkit.gui.widgets.results.graph_view import GraphView
        gv = GraphView()
        # Should not crash.
        gv.focus_node("nonexistent_node")

    def test_reset_after_refresh(self, qapp):
        from lexkit.gui.widgets.results.graph_view import GraphView
        gv = GraphView()
        gv.refresh()
        gv._reset()
        # All nodes and edges should have opacity 1.0 after reset.
        for item in gv._node_items.values():
            assert item.opacity() == 1.0
        for line, _, _ in gv._edge_items:
            assert line.opacity() == 1.0


class TestTableViews:
    def test_stats_view_constructs(self, qapp):
        from lexkit.gui.widgets.results.table_views import StatsView
        sv = StatsView()
        assert sv is not None
        assert sv._label is not None

    def test_stats_view_refresh(self, qapp):
        from lexkit.gui.widgets.results.table_views import StatsView
        sv = StatsView()
        sv.refresh()
        text = sv._label.text()
        # Should contain some HTML table data, even if DB is empty.
        assert "Files indexed" in text or "Error" in text

    def test_references_view_constructs(self, qapp):
        from lexkit.gui.widgets.results.table_views import ReferencesView
        rv = ReferencesView()
        assert rv is not None
        assert rv._table is not None

    def test_references_view_refresh_empty(self, qapp):
        from lexkit.gui.widgets.results.table_views import ReferencesView
        rv = ReferencesView()
        rv.refresh()
        # Table should have 0 rows with empty DB.
        assert rv._table.rowCount() == 0

    def test_clusters_view_constructs(self, qapp):
        from lexkit.gui.widgets.results.table_views import ClustersView
        cv = ClustersView()
        assert cv is not None
        assert cv._tree is not None

    def test_clusters_view_refresh_empty(self, qapp):
        from lexkit.gui.widgets.results.table_views import ClustersView
        cv = ClustersView()
        cv.refresh()
        assert cv._tree.topLevelItemCount() == 0

    def test_references_table_headers(self, qapp):
        from lexkit.gui.widgets.results.table_views import ReferencesView
        rv = ReferencesView()
        headers = [rv._table.horizontalHeaderItem(i).text() for i in range(rv._table.columnCount())]
        assert headers == ["Author", "Year", "Title", "DOI", "URL", "Source"]

    def test_clusters_tree_headers(self, qapp):
        from lexkit.gui.widgets.results.table_views import ClustersView
        cv = ClustersView()
        headers = [cv._tree.headerItem().text(i) for i in range(cv._tree.columnCount())]
        assert headers == ["File", "Cluster", "Similarity"]
