"""Dashboard — one-click "Run Full Pipeline" with live progress + log.

This is the landing panel of the GUI. It exposes the headline feature: pick an
input folder, click **Run Full Pipeline**, and watch scan → clean → search →
refs → cite execute in a background worker with streaming output.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QCheckBox, QProgressBar, QFileDialog, QGroupBox, QFrame,
)

from lexkit.gui.widgets.log_panel import LogPanel
from lexkit.gui.workers import ToolWorker


def _run_full_pipeline(input_dir: str, *, auto_sort: bool, dedup: bool, near_dup: bool) -> None:
    """Execute the full LeXKit pipeline. Runs inside a ToolWorker."""
    from lexkit.pipelines.runner import PipelineRunner

    runner = PipelineRunner(input_path=Path(input_dir))
    runner.run("full")


class Dashboard(QWidget):
    """The one-click pipeline runner panel."""

    pipeline_started = Signal()
    pipeline_finished = Signal()

    def __init__(self, status_bar=None, parent=None) -> None:
        super().__init__(parent)
        self._status_bar = status_bar
        self._worker: ToolWorker | None = None
        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(14)

        # Header
        title = QLabel("▶  Run Full Pipeline")
        title.setStyleSheet("font-size:22px; font-weight:bold; color:#c084fc;")
        root.addWidget(title)
        root.addWidget(QLabel(
            "Scan → Clean → Extract → Search → References → Citation Graph.\n"
            "Runs the entire LeXKit workflow in one click. Output streams below."
        ))

        # Input folder picker
        grp = QGroupBox("Input")
        g = QVBoxLayout(grp)
        row = QHBoxLayout()
        self._input_edit = QLineEdit()
        self._input_edit.setPlaceholderText("Select your research folder…")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._pick_folder)
        row.addWidget(self._input_edit, 1)
        row.addWidget(browse)
        g.addLayout(row)

        # Options
        opt_row = QHBoxLayout()
        self._auto_sort = QCheckBox("Auto-sort files")
        self._auto_sort.setChecked(True)
        self._dedup = QCheckBox("Dedup (exact)")
        self._dedup.setChecked(True)
        self._near_dup = QCheckBox("Near-dup cluster")
        self._near_dup.setChecked(True)
        opt_row.addWidget(self._auto_sort)
        opt_row.addWidget(self._dedup)
        opt_row.addWidget(self._near_dup)
        opt_row.addStretch()
        g.addLayout(opt_row)
        root.addWidget(grp)

        # Big run button + progress
        run_row = QHBoxLayout()
        self._run_btn = QPushButton("▶  Run Full Pipeline")
        self._run_btn.setObjectName("PrimaryButton")
        self._run_btn.setMinimumHeight(48)
        self._run_btn.clicked.connect(self._on_run)
        run_row.addWidget(self._run_btn, 1)
        root.addLayout(run_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate until we get counts
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#45475a;")
        root.addWidget(sep)

        # Live log
        self._log = LogPanel("Live Output")
        root.addWidget(self._log, 1)

    # ── Actions ────────────────────────────────────────────────────────────────
    def _pick_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select research folder")
        if d:
            self._input_edit.setText(d)

    def _on_run(self) -> None:
        input_dir = self._input_edit.text().strip()
        if not input_dir:
            self._log.append_line("[ERROR] Please select an input folder first.")
            return
        if not Path(input_dir).exists():
            self._log.append_line(f"[ERROR] Folder not found: {input_dir}")
            return

        # Disable while running.
        self._run_btn.setEnabled(False)
        self._run_btn.setText("Running…")
        self._progress.setVisible(True)
        self._set_status(f"Running full pipeline on {input_dir}…")
        self.pipeline_started.emit()

        self._worker = ToolWorker(
            _run_full_pipeline,
            kwargs={
                "input_dir": input_dir,
                "auto_sort": self._auto_sort.isChecked(),
                "dedup": self._dedup.isChecked(),
                "near_dup": self._near_dup.isChecked(),
            },
        )
        self._worker.log_line.connect(self._log.append)
        self._worker.finished_ok.connect(self._on_done)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _on_done(self, _result) -> None:
        self._reset_button("✓ Pipeline complete")
        self._set_status("Pipeline finished successfully.")
        self._progress.setVisible(False)
        self.pipeline_finished.emit()

    def _on_fail(self, err: str) -> None:
        self._reset_button("✗ Failed")
        self._log.append_line(f"\n[FAILED] {err}")
        self._set_status(f"Pipeline failed: {err}")
        self._progress.setVisible(False)
        self.pipeline_finished.emit()

    def _reset_button(self, text: str) -> None:
        self._run_btn.setEnabled(True)
        self._run_btn.setText("▶  Run Full Pipeline")
        self._log.append_line(f"\n{'='*60}\n{text}\n{'='*60}")

    def _set_status(self, msg: str) -> None:
        if self._status_bar is not None:
            self._status_bar.showMessage(msg, 8000)

    # Allow other panels to share this log.
    def append_log(self, text: str) -> None:
        self._log.append(text)
