"""Tool panels — individual forms for each of the 9 LeXKit tools.

A sidebar selects a tool; the right pane shows a form with the relevant options
and a Run button. Every Run spawns a :class:`ToolWorker` so the UI never blocks.
Output streams to a shared log.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QComboBox, QDoubleSpinBox, QSpinBox, QFileDialog,
    QGroupBox, QStackedWidget, QScrollArea, QMessageBox,
)

from lexkit.gui.widgets.log_panel import LogPanel
from lexkit.gui.workers import ToolWorker


# ── Helpers ───────────────────────────────────────────────────────────────────

def _folder_picker(line: QLineEdit, parent: QWidget) -> Callable[[], None]:
    def _pick() -> None:
        d = QFileDialog.getExistingDirectory(parent, "Select folder")
        if d:
            line.setText(d)
    return _pick


def _file_picker(line: QLineEdit, parent: QWidget, *, filt: str = "All files (*.*)") -> Callable[[], None]:
    def _pick() -> None:
        f, _ = QFileDialog.getOpenFileName(parent, "Select file", "", filt)
        if f:
            line.setText(f)
    return _pick


def _save_picker(line: QLineEdit, parent: QWidget, *, filt: str = "All files (*.*)") -> Callable[[], None]:
    def _pick() -> None:
        f, _ = QFileDialog.getSaveFileName(parent, "Save as", "", filt)
        if f:
            line.setText(f)
    return _pick


class _ToolPanelBase(QWidget):
    """Base class: a form area + Run button + a log, shared styling."""

    def __init__(self, title: str, description: str, run_fn, parent=None) -> None:
        super().__init__(parent)
        self._run_fn = run_fn
        self._worker: ToolWorker | None = None
        self._fields: dict[str, object] = {}

        root = QVBoxLayout(self)
        root.setSpacing(12)

        lbl = QLabel(title)
        lbl.setStyleSheet("font-size:20px; font-weight:bold; color:#c084fc;")
        root.addWidget(lbl)
        root.addWidget(QLabel(description))

        self._form_container = QGroupBox("Options")
        self._form = QFormLayout(self._form_container)
        self._form.setSpacing(10)
        root.addWidget(self._form_container)

        self._run_btn = QPushButton("▶  Run")
        self._run_btn.setObjectName("PrimaryButton")
        self._run_btn.setMinimumHeight(40)
        self._run_btn.clicked.connect(self._on_run)
        root.addWidget(self._run_btn)

        self._log = LogPanel(f"{title} Output")
        root.addWidget(self._log, 1)

    # ── field registration helpers ────────────────────────────────────────────
    def add_folder(self, key: str, label: str, default: str = "") -> QLineEdit:
        le = QLineEdit(default)
        le.setPlaceholderText("Folder…")
        btn = QPushButton("Browse…")
        btn.clicked.connect(_folder_picker(le, self))
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0,0,0,0)
        h.addWidget(le, 1); h.addWidget(btn)
        self._form.addRow(label, w)
        self._fields[key] = le
        return le

    def add_file(self, key: str, label: str, default: str = "", filt: str = "All files (*.*)") -> QLineEdit:
        le = QLineEdit(default)
        le.setPlaceholderText("File…")
        btn = QPushButton("Browse…")
        btn.clicked.connect(_file_picker(le, self, filt=filt))
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0,0,0,0)
        h.addWidget(le, 1); h.addWidget(btn)
        self._form.addRow(label, w)
        self._fields[key] = le
        return le

    def add_save(self, key: str, label: str, default: str = "", filt: str = "All files (*.*)") -> QLineEdit:
        le = QLineEdit(default)
        le.setPlaceholderText("Output file…")
        btn = QPushButton("Browse…")
        btn.clicked.connect(_save_picker(le, self, filt=filt))
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0,0,0,0)
        h.addWidget(le, 1); h.addWidget(btn)
        self._form.addRow(label, w)
        self._fields[key] = le
        return le

    def add_text(self, key: str, label: str, default: str = "") -> QLineEdit:
        le = QLineEdit(default)
        self._form.addRow(label, le)
        self._fields[key] = le
        return le

    def add_combo(self, key: str, label: str, items: list[str], default: str | None = None) -> QComboBox:
        cb = QComboBox()
        cb.addItems(items)
        if default and default in items:
            cb.setCurrentText(default)
        self._form.addRow(label, cb)
        self._fields[key] = cb
        return cb

    def add_check(self, key: str, label: str, default: bool = True) -> QCheckBox:
        cb = QCheckBox()
        cb.setChecked(default)
        self._form.addRow(label, cb)
        self._fields[key] = cb
        return cb

    def add_spin(self, key: str, label: str, default: int = 0, lo: int = 0, hi: int = 100000) -> QSpinBox:
        sp = QSpinBox()
        sp.setRange(lo, hi); sp.setValue(default)
        self._form.addRow(label, sp)
        self._fields[key] = sp
        return sp

    def add_double(self, key: str, label: str, default: float = 0.0, lo: float = 0.0, hi: float = 1.0, step: float = 0.05) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(lo, hi); sp.setValue(default); sp.setSingleStep(step); sp.setDecimals(2)
        self._form.addRow(label, sp)
        self._fields[key] = sp
        return sp

    # ── value extraction ──────────────────────────────────────────────────────
    def _vals(self) -> dict[str, object]:
        out: dict[str, object] = {}
        for k, w in self._fields.items():
            if isinstance(w, QCheckBox):
                out[k] = w.isChecked()
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                out[k] = w.value()
            elif isinstance(w, QComboBox):
                out[k] = w.currentText()
            else:
                out[k] = w.text().strip()
        return out

    # ── run ───────────────────────────────────────────────────────────────────
    def _on_run(self) -> None:
        vals = self._vals()
        kwargs = self._build_kwargs(vals)
        if kwargs is None:  # validation failed
            return
        self._run_btn.setEnabled(False)
        self._run_btn.setText("Running…")
        self._worker = ToolWorker(self._run_fn, kwargs=kwargs)
        self._worker.log_line.connect(self._log.append)
        self._worker.finished_ok.connect(lambda r: self._done())
        self._worker.failed.connect(self._fail)
        self._worker.start()

    def _build_kwargs(self, vals: dict[str, object]) -> dict | None:
        """Override in subclasses: map form values → tool kwargs. Return None to abort."""
        return {k: v for k, v in vals.items()}

    def _done(self) -> None:
        self._run_btn.setEnabled(True)
        self._run_btn.setText("▶  Run")
        self._log.append_line("\n✓ Done.\n")

    def _fail(self, err: str) -> None:
        self._run_btn.setEnabled(True)
        self._run_btn.setText("▶  Run")
        self._log.append_line(f"\n✗ Failed: {err}\n")


# ── Concrete tool panels ──────────────────────────────────────────────────────

class FsmPanel(_ToolPanelBase):
    def __init__(self, parent=None):
        super().__init__("File System Manager", "Scan, sort, deduplicate and near-duplicate cluster your library.",
                         _fsm_run, parent)
        self.add_folder("directory", "Scan folder")
        self.add_check("auto_sort", "Auto-sort into year/topic folders", True)
        self.add_check("find_duplicates", "Detect exact duplicates", True)
        self.add_check("cluster", "Near-duplicate clustering (MinHash)", True)
        self.add_check("recursive", "Recursive", True)
        self.add_combo("export", "Export metadata", ["", "json", "csv"], "")

def _fsm_run(directory, auto_sort, find_duplicates, cluster, recursive, export, **_):
    from lexkit.tools import fsm
    if export:
        fsm.scan(directory=directory, auto_sort=auto_sort, find_duplicates=find_duplicates,
                 cluster_near_dups=cluster, recursive=recursive, export=export, output=None)
    else:
        fsm.scan(directory=directory, auto_sort=auto_sort, find_duplicates=find_duplicates,
                 cluster_near_dups=cluster, recursive=recursive, export=None, output=None)


class CleanPanel(_ToolPanelBase):
    def __init__(self, parent=None):
        super().__init__("Document Cleaner", "Fix PDFs, normalize encoding, remove junk characters.",
                         _clean_run, parent)
        self.add_folder("input_path", "Input folder")
        self.add_check("fix_encoding", "Fix encoding", True)
        self.add_check("recursive", "Recursive", True)
        self.add_check("dry_run", "Dry run (preview only)", False)

def _clean_run(input_path, fix_encoding, recursive, dry_run, **_):
    from lexkit.tools import clean
    clean.run(input_path=input_path, recursive=recursive, fix_encoding=fix_encoding, dry_run=dry_run, output_dir=None)


class BatchPanel(_ToolPanelBase):
    def __init__(self, parent=None):
        super().__init__("Batch Processor", "Rename files by pattern or extract text from PDFs.",
                         _batch_run, parent)
        self.add_combo("mode", "Operation", ["extract", "rename"], "extract")
        self.add_folder("input_path", "Input folder")
        self.add_text("pattern", "Rename pattern", "{year}_{author}_{stem}")
        self.add_combo("fmt", "Extract format", ["txt", "md"], "txt")
        self.add_check("recursive", "Recursive", True)

def _batch_run(mode, input_path, pattern, fmt, recursive, **_):
    from lexkit.tools import batch
    if mode == "rename":
        batch.rename(input_path=input_path, pattern=pattern, recursive=recursive)
    else:
        batch.extract(input_path=input_path, output_dir=None, fmt=fmt, recursive=recursive)


class SearchPanel(_ToolPanelBase):
    def __init__(self, parent=None):
        super().__init__("Search Engine", "Full-text, regex, fuzzy search + TF-IDF similarity.",
                         _search_run, parent)
        self.add_combo("mode", "Operation", ["index", "query", "similar"], "index")
        self.add_folder("directory", "Library folder")
        self.add_text("search_query", "Query", "")
        self.add_file("to", "Anchor file (for 'similar')", "", "Documents (*.pdf *.txt *.md *.tex)")
        self.add_check("use_regex", "Regex mode", False)
        self.add_check("fuzzy", "Fuzzy mode", False)
        self.add_double("threshold", "Similarity threshold", 0.25, 0.0, 1.0, 0.05)
        self.add_spin("limit", "Result limit", 20, 1, 1000)

def _search_run(mode, directory, search_query, to, use_regex, fuzzy, threshold, limit, **_):
    from lexkit.tools import search
    if mode == "index":
        search.index(directory=directory, rebuild=False)
    elif mode == "query":
        search.query(search_query=search_query, directory=directory, use_regex=use_regex, fuzzy=fuzzy, field="content", limit=limit)
    elif mode == "similar":
        search.similar(directory=directory, to=to, threshold=threshold, limit=limit)


class RefsPanel(_ToolPanelBase):
    def __init__(self, parent=None):
        super().__init__("Reference Manager", "Extract citations (APA/MLA/Chicago/Harvard/bracket) and export.",
                         _refs_run, parent)
        self.add_combo("mode", "Operation", ["extract", "list", "export"], "extract")
        self.add_folder("input_path", "Input folder (extract)")
        self.add_combo("fmt", "Export format", ["bibtex", "apa", "mla", "chicago"], "bibtex")
        self.add_save("output", "Export output file", "bibliography.bib", "BibTeX (*.bib);;Text (*.txt)")
        self.add_check("use_llm", "Use LLM enrichment (if configured)", False)
        self.add_check("recursive", "Recursive", True)
        self.add_spin("limit", "List limit", 50, 1, 100000)

    def _build_kwargs(self, vals):
        m = vals["mode"]
        if m == "extract":
            return {"mode": "extract", "input_path": vals["input_path"], "use_llm": vals["use_llm"], "recursive": vals["recursive"]}
        if m == "list":
            return {"mode": "list", "limit": vals["limit"]}
        return {"mode": "export", "fmt": vals["fmt"], "output": vals["output"] or None}

def _refs_run(mode, **kw):
    from lexkit.tools import refs
    if mode == "extract":
        refs.extract(input_path=kw["input_path"], recursive=kw["recursive"], use_llm=kw["use_llm"])
    elif mode == "list":
        refs.list_refs(limit=kw["limit"])
    elif mode == "export":
        refs.export(fmt=kw["fmt"], output=kw.get("output"))


class CitePanel(_ToolPanelBase):
    def __init__(self, parent=None):
        super().__init__("Citation Graph", "Build a who-cites-whom network and export to GraphML/JSON/DOT.",
                         _cite_run, parent)
        self.add_combo("mode", "Operation", ["build", "graph", "stats", "list"], "build")
        self.add_folder("input_path", "Library folder (build)")
        self.add_combo("fmt", "Export format", ["graphml", "json", "dot"], "graphml")
        self.add_save("output", "Export output file", "citation_graph.graphml", "GraphML (*.graphml);;JSON (*.json);;DOT (*.dot)")
        self.add_double("threshold", "Match threshold", 0.25, 0.0, 1.0, 0.05)
        self.add_spin("limit", "List limit", 50, 1, 100000)

    def _build_kwargs(self, vals):
        m = vals["mode"]
        if m == "build":
            return {"mode": "build", "input_path": vals["input_path"], "threshold": vals["threshold"]}
        if m == "graph":
            return {"mode": "graph", "fmt": vals["fmt"], "output": vals["output"] or None}
        if m == "stats":
            return {"mode": "stats"}
        return {"mode": "list", "limit": vals["limit"]}

def _cite_run(mode, **kw):
    from lexkit.tools import cite
    if mode == "build":
        cite.build(input_path=kw["input_path"], threshold=kw["threshold"], recursive=True)
    elif mode == "graph":
        cite.graph(export=kw["fmt"], output=kw.get("output"))
    elif mode == "stats":
        cite.stats()
    elif mode == "list":
        cite.list_edges(limit=kw["limit"])


class NotesPanel(_ToolPanelBase):
    def __init__(self, parent=None):
        super().__init__("Notes Compiler", "Merge note files and deduplicate (exact + near-dup).",
                         _notes_run, parent)
        self.add_folder("input_path", "Notes folder")
        self.add_check("dedup", "Exact dedup", True)
        self.add_check("near_dup", "Near-dup dedup (MinHash)", True)
        self.add_double("near_dup_threshold", "Near-dup threshold", 0.7, 0.0, 1.0, 0.05)
        self.add_check("recursive", "Recursive", True)
        self.add_combo("sort_by", "Sort by", ["name", "size"], "name")
        self.add_save("output", "Output file", "compiled_notes.md", "Markdown (*.md)")

    def _build_kwargs(self, vals):
        return {**vals, "output": vals["output"] or None}

def _notes_run(**kw):
    from lexkit.tools import notes
    notes.run(**kw)


class TplPanel(_ToolPanelBase):
    def __init__(self, parent=None):
        super().__init__("Template Generator", "Generate APA/IEEE/ACM/MLA/Markdown paper stubs.",
                         _tpl_run, parent)
        self.add_combo("fmt", "Format", ["apa", "ieee", "acm", "mla", "markdown"], "apa")
        self.add_text("title", "Title", "Research Paper Title")
        self.add_text("author", "Author", "Author Name")
        self.add_save("output", "Output file", "paper_apa.tex", "LaTeX (*.tex);;Markdown (*.md)")

    def _build_kwargs(self, vals):
        return {**vals, "output": vals["output"] or None}

def _tpl_run(**kw):
    from lexkit.tools import tpl
    tpl.generate(fmt=kw["fmt"], title=kw["title"], author=kw["author"], output=kw.get("output"))


class SplitPanel(_ToolPanelBase):
    def __init__(self, parent=None):
        super().__init__("Lecture Splitter", "Split a PDF by its table of contents.",
                         _split_run, parent)
        self.add_file("input_path", "Input PDF", "", "PDF (*.pdf)")
        self.add_folder("output", "Output folder")
        self.add_spin("min_pages", "Min pages per section", 2, 1, 1000)
        self.add_check("show_toc", "Show TOC only (preview)", False)

    def _build_kwargs(self, vals):
        if not vals.get("input_path"):
            QMessageBox.warning(self, "Missing input", "Please select an input PDF.")
            return None
        return vals

def _split_run(input_path, output, min_pages, show_toc, **_):
    from lexkit.tools import split
    split.run(input_file=input_path, output_dir=output or None, min_pages=min_pages, show_toc=show_toc)


# ── Registry ──────────────────────────────────────────────────────────────────

TOOL_PANELS: dict[str, type[_ToolPanelBase]] = {
    "fsm":    FsmPanel,
    "clean":  CleanPanel,
    "batch":  BatchPanel,
    "search": SearchPanel,
    "refs":   RefsPanel,
    "cite":   CitePanel,
    "notes":  NotesPanel,
    "tpl":    TplPanel,
    "split":  SplitPanel,
}
