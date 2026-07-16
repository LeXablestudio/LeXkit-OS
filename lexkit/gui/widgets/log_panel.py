"""Log panel — streaming, colorized console output.

Renders the ANSI-coloured text that rich emits (captured via output_capture).
Supports plain append + ANSI escape-sequence translation to Qt's HTML subset.
Auto-scrolls to the bottom as new output arrives.
"""

from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QPushButton, QHBoxLayout

# ── ANSI → Qt colour mapping (the subset rich actually emits) ─────────────────
_ANSI_COLORS = {
    "30": "#45475a", "31": "#f38ba8", "32": "#a6e3a1", "33": "#f9e2af",
    "34": "#89b4fa", "35": "#c084fc", "36": "#89dceb", "37": "#cdd6f4",
    "90": "#585b70", "91": "#f38ba8", "92": "#a6e3a1", "93": "#f9e2af",
    "94": "#89b4fa", "95": "#c084fc", "96": "#89dceb", "97": "#ffffff",
}

_ANSI_RE = re.compile(r"\x1b\[(\d+)(?:;(\d+))?m")
# Strip non-SGR control sequences (cursor moves, OSC, etc.) but PRESERVE color
# codes (\x1b[..m) which the _ANSI_RE parser handles. Use a negative lookahead
# so the trailing 'm' is excluded from the blanket strip.
_CONTROL_RE = re.compile(r"\x1b\[[0-9;]*(?!m)[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[()][AB0]")


def ansi_to_html(text: str) -> str:
    """Convert ANSI escape codes to Qt-compatible HTML, escaping the rest."""
    # Strip non-color control sequences (cursor moves, OSC, etc.)
    text = _CONTROL_RE.sub("", text)
    # Replace color codes with <span style="color:..."> tags.
    out: list[str] = []
    pos = 0
    open_spans = 0
    for m in _ANSI_RE.finditer(text):
        out.append(_escape(text[pos:m.start()]))
        pos = m.end()
        code = m.group(1)
        if code == "0":  # reset
            for _ in range(open_spans):
                out.append("</span>")
            open_spans = 0
        elif code in _ANSI_COLORS:
            out.append(f'<span style="color:{_ANSI_COLORS[code]}">')
            open_spans += 1
    out.append(_escape(text[pos:]))
    for _ in range(open_spans):
        out.append("</span>")
    return "".join(out)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")


class LogPanel(QWidget):
    """A read-only streaming log with ANSI colour + a Clear button."""

    def __init__(self, title: str = "Output", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header row with clear button.
        header = QHBoxLayout()
        from PySide6.QtWidgets import QLabel
        header.addWidget(QLabel(f"▶ {title}"))
        header.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear)
        header.addWidget(clear_btn)
        layout.addLayout(header)

        self._edit = QPlainTextEdit()
        self._edit.setReadOnly(True)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self._edit.setFont(font)
        self._edit.setStyleSheet(
            f"background-color:#181825; color:#cdd6f4; border:1px solid #45475a; border-radius:4px;"
        )
        layout.addWidget(self._edit)

    def append(self, text: str) -> None:
        """Append a chunk of (possibly ANSI-coloured) text to the log."""
        if not text:
            return
        html = ansi_to_html(text)
        self._edit.appendHtml(html)
        # Auto-scroll to bottom.
        self._edit.moveCursor(QTextCursor.End)

    def append_line(self, text: str) -> None:
        """Append a single line."""
        self.append(text)

    def clear(self) -> None:
        self._edit.clear()
