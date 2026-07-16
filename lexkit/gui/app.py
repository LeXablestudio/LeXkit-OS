"""Main application window — sidebar navigation + stacked content.

Ties together the Dashboard (one-click pipeline), the 9 tool panels, and the
result viewers (references, clusters, stats, citation graph) into a single
LeXKit desktop window.

Run with: ``python -m lexkit.gui``  or  ``lexkit-gui``.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QButtonGroup, QStackedWidget, QLabel, QStatusBar,
    QScrollArea, QSplitter,
)

from lexkit import __version__
from lexkit.gui.theme import apply_theme
from lexkit.gui.widgets.dashboard import Dashboard
from lexkit.gui.widgets.tool_panels import TOOL_PANELS
from lexkit.gui.widgets.results import ReferencesView, ClustersView, StatsView, GraphView


# ── Sidebar entries (label → icon glyph, whether it's a tool) ─────────────────
SIDEBAR = [
    ("📊  Dashboard",        "dashboard",    False),
    ("────────────────",     None,           None),   # separator
    ("🗂  File Manager",     "fsm",          True),
    ("🧹  Cleaner",          "clean",        True),
    ("⚙  Batch",            "batch",        True),
    ("🔍  Search",           "search",       True),
    ("📑  References",       "refs",         True),
    ("🔗  Citation Graph",   "cite",         True),
    ("📝  Notes",            "notes",        True),
    ("📄  Templates",        "tpl",          True),
    ("✂  Splitter",         "split",        True),
    ("────────────────",     None,           None),   # separator
    ("📊  Statistics",       "stats",        False),
    ("📑  Refs Table",       "refs_view",    False),
    ("🧬  Clusters",         "clusters",     False),
    ("🕸  Graph View",       "graph",        False),
]


class SidebarButton(QPushButton):
    """A flat, checkable sidebar button."""

    def __init__(self, text: str, key: str, parent=None) -> None:
        super().__init__(text, parent)
        self.key = key
        self.setObjectName("Sidebar")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)


class MainWindow(QMainWindow):
    """The LeXKit desktop application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"LeXKit v{__version__} — Research OS")
        self.resize(1280, 820)
        self.setMinimumSize(960, 600)

        # Central splitter: sidebar | content.
        central = QWidget()
        self.setCentralWidget(central)
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # Status bar must exist before content is built (panels reference it).
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready. Select an option from the sidebar.")

        self._build_sidebar(h)
        self._build_content(h)

        # Default to dashboard.
        self._nav_group.button(0).setChecked(True)
        self._switch_to(0)

    # ── Sidebar ───────────────────────────────────────────────────────────────
    def _build_sidebar(self, parent_layout: QHBoxLayout) -> None:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        sv = QVBoxLayout(sidebar)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(0)

        # Brand.
        brand = QLabel("LeX<font color='#cdd6f4'>Kit</font>")
        brand.setObjectName("BrandLabel")
        sv.addWidget(brand)
        ver = QLabel(f"<div style='padding-left:16px; color:#a6adc8;'>v{__version__}</div>")
        sv.addWidget(ver)
        sv.addSpacing(8)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._buttons: list[QPushButton] = []
        idx = 0
        for label, key, is_tool in SIDEBAR:
            if key is None:  # separator
                sep = QLabel(label.replace("─", ""))
                sep.setFixedHeight(12)
                sv.addWidget(sep)
                continue
            btn = SidebarButton(label, key)
            if idx == 0:
                btn.setChecked(True)
            self._nav_group.addButton(btn, idx)
            btn.clicked.connect(lambda _checked=False, i=idx: self._switch_to(i))
            sv.addWidget(btn)
            self._buttons.append(btn)
            idx += 1
        sv.addStretch()

        parent_layout.addWidget(sidebar)

    # ── Content stack ─────────────────────────────────────────────────────────
    def _build_content(self, parent_layout: QHBoxLayout) -> None:
        self._stack = QStackedWidget()

        # 0 — Dashboard.
        self._dashboard = Dashboard(status_bar=self._status)
        self._dashboard.pipeline_finished.connect(self._refresh_results)
        scroll0 = self._wrap_scroll(self._dashboard)
        self._stack.addWidget(scroll0)

        # Tool panels (9).
        self._tool_panels: dict[str, object] = {}
        for label, key, is_tool in SIDEBAR:
            if not is_tool:
                continue
            panel_cls = TOOL_PANELS[key]
            panel = panel_cls()
            self._tool_panels[key] = panel
            self._stack.addWidget(self._wrap_scroll(panel))

        # Result viewers.
        self._stats_view = StatsView()
        self._refs_view = ReferencesView()
        self._clusters_view = ClustersView()
        self._graph_view = GraphView()
        self._stack.addWidget(self._wrap_scroll(self._stats_view))
        self._stack.addWidget(self._wrap_scroll(self._refs_view))
        self._stack.addWidget(self._wrap_scroll(self._clusters_view))
        self._stack.addWidget(self._graph_view)  # graph: no scroll (own view)

        parent_layout.addWidget(self._stack, 1)

    def _wrap_scroll(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        scroll.setFrameShape(QScrollArea.NoFrame)
        return scroll

    # ── Navigation ────────────────────────────────────────────────────────────
    def _switch_to(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)
        # Refresh result views when shown.
        widget = self._stack.widget(idx)
        inner = widget.widget() if isinstance(widget, QScrollArea) else widget
        if hasattr(inner, "refresh"):
            inner.refresh()
        # Update status.
        btn = self._nav_group.button(idx)
        if btn:
            self._status.showMessage(f"View: {btn.text().strip()}")

    def _refresh_results(self) -> None:
        """Called after a pipeline/tool finishes — refresh all data views."""
        for view in (self._stats_view, self._refs_view, self._clusters_view, self._graph_view):
            try:
                view.refresh()
            except Exception:
                pass


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    """Launch the LeXKit GUI. Returns an exit code."""
    # High DPI handling.
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("LeXKit")
    app.setApplicationVersion(__version__)
    apply_theme(app)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
