"""Interactive citation-graph network viewer.

Draws the who-cites-whom network as nodes (files) connected by directed edges
(citations), positioned by a **deterministic seeded spring layout** so the same
graph always renders identically (honouring LeXKit's reproducibility promise).

Features
--------
- Pan & zoom (native QGraphicsView).
- Click a node → highlight its neighbours + edges; dim the rest.
- Hover → tooltip with file name + degree.
- Score-based edge thickness + colour (higher score = brighter magenta).
- Node size proportional to in-degree (most-cited = biggest).
- Reads ``citation_edges`` from the SQLite store; refresh button.

The layout is a pure-Python Fruchterman–Reingold with a fixed seed and fixed
iteration count — no randomness across runs.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QPainterPath, QPolygonF
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsLineItem,
    QGraphicsTextItem, QMessageBox, QSlider,
)

from lexkit.config.settings import Settings
from lexkit.db.store import get_db, list_citation_edges

# ── Deterministic spring layout (Fruchterman–Reingold) ────────────────────────

def compute_layout(
    nodes: list[str],
    edges: list[tuple[str, str, float]],
    *,
    width: float = 800.0,
    height: float = 600.0,
    iterations: int = 300,
    seed: int = 42,
) -> dict[str, tuple[float, float]]:
    """Deterministic FR layout. Same (nodes, edges, seed) → identical positions."""
    if not nodes:
        return {}
    rng = random.Random(seed)
    n = len(nodes)
    area = width * height
    k = math.sqrt(area / max(n, 1)) * 0.8  # optimal distance
    k2 = k * k

    # Initial random positions (seeded → reproducible).
    pos: dict[str, list[float]] = {
        node: [rng.uniform(0, width), rng.uniform(0, height)] for node in nodes
    }

    adj = {e[0] for e in edges} | {e[1] for e in edges}
    edge_list = [(e[0], e[1]) for e in edges]

    for _it in range(iterations):
        disp: dict[str, list[float]] = {node: [0.0, 0.0] for node in nodes}
        # Repulsive forces between all pairs.
        for i in range(n):
            u = nodes[i]
            for j in range(n):
                if i == j:
                    continue
                v = nodes[j]
                dx = pos[u][0] - pos[v][0]
                dy = pos[u][1] - pos[v][1]
                d2 = dx * dx + dy * dy + 0.01
                if d2 < k2 * 25:  # only nearby pairs (perf)
                    factor = k2 / d2
                    disp[u][0] += dx / math.sqrt(d2) * factor
                    disp[u][1] += dy / math.sqrt(d2) * factor
        # Attractive forces along edges.
        for u, v in edge_list:
            dx = pos[u][0] - pos[v][0]
            dy = pos[u][1] - pos[v][1]
            d = math.sqrt(dx * dx + dy * dy) + 0.01
            factor = d * d / k
            fx = dx / d * factor
            fy = dy / d * factor
            disp[u][0] -= fx
            disp[u][1] -= fy
            disp[v][0] += fx
            disp[v][1] += fy
        # Apply displacement with cooling + frame.
        cool = 1.0 - _it / iterations
        max_disp = width * 0.1 * cool
        for node in nodes:
            dx, dy = disp[node]
            d = math.sqrt(dx * dx + dy * dy) + 0.01
            step = min(d, max_disp)
            pos[node][0] = max(20, min(width - 20, pos[node][0] + dx / d * step))
            pos[node][1] = max(20, min(height - 20, pos[node][1] + dy / d * step))

    return {node: (p[0], p[1]) for node, p in pos.items()}


# ── Qt node item with hover/click ─────────────────────────────────────────────

class _NodeItem(QGraphicsEllipseItem):
    """A graph node. Stores its key + neighbours for highlighting."""

    def __init__(self, key: str, x: float, y: float, radius: float, in_degree: int, view: "GraphView"):
        super().__init__(x - radius, y - radius, radius * 2, radius * 2)
        self.key = key
        self.radius = radius
        self.in_degree = in_degree
        self._view = view
        self._base_color = QColor("#89dceb")
        self.setBrush(QBrush(self._base_color))
        self.setPen(QPen(QColor("#45475a"), 1.5))
        self.setZValue(10)
        self.setAcceptHoverEvents(True)
        self.setToolTip(f"{Path(key).name}\nIn-degree: {in_degree}")
        self.setFlag(QGraphicsEllipseItem.ItemIsSelectable, True)

    def hoverEnterEvent(self, e):
        self.setBrush(QBrush(QColor("#f9e2af")))
        self.setScale(1.25)
        super().hoverEnterEvent(e)

    def hoverLeaveEvent(self, e):
        self.setScale(1.0)
        if not self.isSelected():
            self.setBrush(QBrush(self._base_color))
        super().hoverLeaveEvent(e)

    def mousePressEvent(self, e):
        self._view.focus_node(self.key)
        super().mousePressEvent(e)


# ── The main graph view ───────────────────────────────────────────────────────

class GraphView(QWidget):
    """Interactive citation-network diagram, backed by the SQLite store."""

    NODE_COLORS = ["#89dceb", "#a6e3a1", "#fab387", "#f9e2af", "#cba6f7"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._edges_data: list[dict] = []
        self._node_items: dict[str, _NodeItem] = {}
        self._edge_items: list[tuple[QGraphicsLineItem, str, str]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        v = QVBoxLayout(self)
        # Header
        h = QHBoxLayout()
        title = QLabel("🔗  Citation Graph")
        title.setStyleSheet("font-size:18px; font-weight:bold; color:#c084fc;")
        h.addWidget(title); h.addStretch()
        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color:#a6adc8;")
        h.addWidget(self._count_label)
        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self.refresh)
        h.addWidget(btn_refresh)
        btn_reset = QPushButton("↩  Reset view")
        btn_reset.clicked.connect(self._reset)
        h.addWidget(btn_reset)
        v.addLayout(h)

        # Hint
        hint = QLabel("Click a node to highlight its citations · scroll to zoom · drag to pan")
        hint.setStyleSheet("color:#585b70; font-style:italic;")
        v.addWidget(hint)

        # The scene + view
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(0, 0, 1000, 750)
        self._gview = QGraphicsView(self._scene)
        self._gview.setRenderHint(self._gview.renderHints(), True)
        self._gview.setDragMode(QGraphicsView.ScrollHandDrag)
        self._gview.setStyleSheet("background-color:#181825; border:1px solid #45475a;")
        v.addWidget(self._gview, 1)

        self.refresh()

    def load_edges(self) -> list[dict]:
        """Pull citation edges from the DB."""
        try:
            settings = Settings.load_default()
            db = get_db(settings.db_path)
            edges = list_citation_edges(db)
            db.close()
            return edges
        except Exception:
            return []

    def refresh(self) -> None:
        self._scene.clear()
        self._node_items.clear()
        self._edge_items.clear()
        self._edges_data = self.load_edges()

        if not self._edges_data:
            placeholder = self._scene.addText(
                "No citation edges yet.\n\nRun 'Citation Graph → build' from the Tools tab,\n"
                "or the full pipeline, to populate the graph.",
                QFont("Segoe UI", 12),
            )
            placeholder.setDefaultTextColor(QColor("#a6adc8"))
            placeholder.setPos(200, 300)
            self._count_label.setText("")
            return

        # Collect nodes + in-degrees.
        in_deg = Counter(e["target_file"] for e in self._edges_data)
        out_deg = Counter(e["source_file"] for e in self._edges_data)
        nodes = sorted(set(in_deg) | set(out_deg))

        # Deterministic layout.
        layout = compute_layout(nodes, [(e["source_file"], e["target_file"], e.get("score", 0)) for e in self._edges_data])

        # Draw edges first (so nodes sit on top).
        max_score = max((e.get("score", 0) for e in self._edges_data), default=1.0) or 1.0
        for e in self._edges_data:
            s, t = e["source_file"], e["target_file"]
            if s not in layout or t not in layout:
                continue
            x1, y1 = layout[s]
            x2, y2 = layout[t]
            line = self._scene.addLine(x1, y1, x2, y2)
            score = e.get("score", 0)
            intensity = 0.35 + 0.65 * (score / max_score)
            pen = QPen(QColor.fromRgbF(0.42, 0.16, 0.85, intensity), 1.2 + 1.5 * (score / max_score))
            line.setPen(pen)
            line.setZValue(1)
            self._edge_items.append((line, s, t))

        # Draw nodes.
        max_in = max(in_deg.values(), default=1) or 1
        for node in nodes:
            x, y = layout[node]
            deg = in_deg.get(node, 0)
            radius = 8 + 16 * (deg / max_in)  # bigger = more cited
            item = _NodeItem(node, x, y, radius, deg, self)
            if deg == 0:
                item._base_color = QColor("#f38ba8")  # uncited = red
                item.setBrush(QBrush(item._base_color))
            self._scene.addItem(item)
            self._node_items[node] = item

            # Label under the node.
            label = self._scene.addText(Path(node).name, QFont("Segoe UI", 8))
            label.setDefaultTextColor(QColor("#cdd6f4"))
            label.setPos(x - label.boundingRect().width() / 2, y + radius + 2)
            label.setZValue(9)

        self._count_label.setText(f"{len(nodes)} nodes · {len(self._edges_data)} edges")

    def focus_node(self, key: str) -> None:
        """Highlight a node's neighbourhood; dim everything else."""
        if key not in self._node_items:
            return
        # Find neighbours.
        neighbours = {key}
        for e in self._edges_data:
            if e["source_file"] == key:
                neighbours.add(e["target_file"])
            if e["target_file"] == key:
                neighbours.add(e["source_file"])
        # Dim non-neighbours.
        for k, item in self._node_items.items():
            if k in neighbours:
                item.setOpacity(1.0)
                item.setBrush(QBrush(QColor("#f9e2af")))
            else:
                item.setOpacity(0.25)
                item.setBrush(QBrush(item._base_color))
        # Dim non-adjacent edges.
        for line, s, t in self._edge_items:
            if s == key or t == key:
                line.setOpacity(1.0)
            else:
                line.setOpacity(0.1)

    def _reset(self) -> None:
        """Clear highlighting and reset zoom."""
        for item in self._node_items.values():
            item.setOpacity(1.0)
            item.setBrush(QBrush(item._base_color))
            item.setSelected(False)
        for line, _, _ in self._edge_items:
            line.setOpacity(1.0)
        self._gview.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
