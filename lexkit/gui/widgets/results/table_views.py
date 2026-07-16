"""Database-backed result viewers: References table + Near-dup clusters tree.

These read directly from the LeXKit SQLite store via :mod:`lexkit.db.store` and
refresh on demand (e.g. after a tool run completes).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QMessageBox,
)

from lexkit.config.settings import Settings
from lexkit.db.store import (
    get_db, list_references, list_near_duplicates, get_stats,
    list_citation_edges,
)


class ReferencesView(QWidget):
    """Sortable table of all stored references."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.addWidget(self._header())
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["Author", "Year", "Title", "DOI", "URL", "Source"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSortingEnabled(True)
        v.addWidget(self._table, 1)
        self.refresh()

    def _header(self) -> QWidget:
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0)
        title = QLabel("📑  References")
        title.setStyleSheet("font-size:18px; font-weight:bold; color:#c084fc;")
        h.addWidget(title); h.addStretch()
        btn = QPushButton("🔄 Refresh")
        btn.clicked.connect(self.refresh)
        h.addWidget(btn)
        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color:#a6adc8;")
        h.addWidget(self._count_label)
        return w

    def refresh(self) -> None:
        try:
            settings = Settings.load_default()
            db = get_db(settings.db_path)
            refs = list_references(db, limit=100000)
            db.close()
            self._table.setSortingEnabled(False)
            self._table.setRowCount(len(refs))
            for i, r in enumerate(refs):
                self._table.setItem(i, 0, QTableWidgetItem(r.get("author") or ""))
                self._table.setItem(i, 1, QTableWidgetItem(r.get("year") or ""))
                self._table.setItem(i, 2, QTableWidgetItem(r.get("title") or ""))
                self._table.setItem(i, 3, QTableWidgetItem(r.get("doi") or ""))
                self._table.setItem(i, 4, QTableWidgetItem(r.get("url") or ""))
                self._table.setItem(i, 5, QTableWidgetItem((r.get("source_file") or "").split("/")[-1]))
            self._table.setSortingEnabled(True)
            self._count_label.setText(f"{len(refs)} references")
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Could not load references:\n{exc}")


class ClustersView(QWidget):
    """Tree of near-duplicate clusters (cluster → member files)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.addWidget(self._header())
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["File", "Cluster", "Similarity"])
        self._tree.setAlternatingRowColors(True)
        v.addWidget(self._tree, 1)
        self.refresh()

    def _header(self) -> QWidget:
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0)
        title = QLabel("🧬  Near-Duplicate Clusters")
        title.setStyleSheet("font-size:18px; font-weight:bold; color:#c084fc;")
        h.addWidget(title); h.addStretch()
        btn = QPushButton("🔄 Refresh")
        btn.clicked.connect(self.refresh)
        h.addWidget(btn)
        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color:#a6adc8;")
        h.addWidget(self._count_label)
        return w

    def refresh(self) -> None:
        try:
            settings = Settings.load_default()
            db = get_db(settings.db_path)
            dups = list_near_duplicates(db)
            db.close()
            self._tree.clear()
            # Group by cluster_id.
            clusters: dict[int | None, list] = {}
            for d in dups:
                clusters.setdefault(d.get("cluster_id"), []).append(d)
            for cid, members in sorted(clusters.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)):
                if cid is None:
                    continue  # skip un-clustered singletons
                label = f"Cluster {cid}  ({len(members)} files)"
                root = QTreeWidgetItem([label, str(cid), ""])
                root.setForeground(0, self.palette().accent())  # type: ignore[arg-type]
                for m in members:
                    sim = m.get("similarity")
                    child = QTreeWidgetItem([
                        (m.get("name") or "").split("/")[-1],
                        str(cid),
                        f"{sim:.2f}" if sim is not None else "—",
                    ])
                    root.addChild(child)
                self._tree.addTopLevelItem(root)
            self._tree.expandAll()
            n_clusters = sum(1 for c in clusters if c is not None)
            self._count_label.setText(f"{n_clusters} clusters, {len(dups)} files")
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Could not load clusters:\n{exc}")


class StatsView(QWidget):
    """A compact readout of overall DB statistics."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        v = QVBoxLayout(self)
        title = QLabel("📊  Database Statistics")
        title.setStyleSheet("font-size:18px; font-weight:bold; color:#c084fc;")
        v.addWidget(title)
        self._label = QLabel("Loading…")
        self._label.setStyleSheet("font-size:15px; color:#cdd6f4;")
        v.addWidget(self._label)
        v.addStretch()
        btn = QPushButton("🔄 Refresh")
        btn.clicked.connect(self.refresh)
        v.addWidget(btn)
        self.refresh()

    def refresh(self) -> None:
        try:
            settings = Settings.load_default()
            s = get_stats(settings.db_path)
            self._label.setText(
                f"<table cellpadding='6'>"
                f"<tr><td>📂 Files indexed:</td><td><b>{s['files']}</b></td></tr>"
                f"<tr><td>📑 References:</td><td><b>{s['refs']}</b></td></tr>"
                f"<tr><td>🔗 Citation edges:</td><td><b>{s['citation_edges']}</b></td></tr>"
                f"<tr><td>🧬 Near-dup clusters:</td><td><b>{s['near_dup_clusters']}</b></td></tr>"
                f"<tr><td>💾 Database size:</td><td><b>{s['size_mb']:.2f} MB</b></td></tr>"
                f"</table>"
            )
        except Exception as exc:
            self._label.setText(f"Error: {exc}")
