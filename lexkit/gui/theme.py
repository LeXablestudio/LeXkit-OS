"""Dark theme + magenta identity for the LeXKit GUI.

Applied via a Qt stylesheet so every widget inherits the look without per-widget
styling. Magenta (#6D28D9) is LeXKit's brand colour; cyan/green/yellow/red mirror
the rich console palette the CLI already uses.
"""

from __future__ import annotations

#: LeXKit brand palette.
COLORS = {
    "bg":        "#1e1e2e",   # main background (dark slate)
    "bg_alt":    "#181825",   # sidebar / panels
    "surface":   "#313244",   # inputs, tables
    "border":    "#45475a",
    "magenta":   "#6D28D9",   # primary accent
    "magenta_lt":"#c084fc",
    "cyan":      "#89dceb",
    "green":     "#a6e3a1",
    "yellow":    "#f9e2af",
    "red":       "#f38ba8",
    "text":      "#cdd6f4",
    "text_dim":  "#a6adc8",
}

QSS = f"""
QWidget {{
    background-color: {COLORS['bg']};
    color: {COLORS['text']};
    font-family: 'Segoe UI', 'DejaVu Sans', sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background-color: {COLORS['bg']};
}}
/* Sidebar */
#Sidebar {{
    background-color: {COLORS['bg_alt']};
    border-right: 1px solid {COLORS['border']};
}}
#Sidebar QPushButton {{
    text-align: left;
    padding: 10px 16px;
    border: none;
    border-left: 3px solid transparent;
    color: {COLORS['text_dim']};
    background: transparent;
    font-size: 14px;
}}
#Sidebar QPushButton:hover {{
    color: {COLORS['text']};
    background-color: {COLORS['surface']};
}}
#Sidebar QPushButton:checked {{
    color: {COLORS['magenta_lt']};
    border-left: 3px solid {COLORS['magenta']};
    background-color: {COLORS['surface']};
}}
/* Brand label */
#BrandLabel {{
    color: {COLORS['magenta_lt']};
    font-size: 18px;
    font-weight: bold;
    padding: 16px;
}}
/* Primary button */
QPushButton#PrimaryButton {{
    background-color: {COLORS['magenta']};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 12px 24px;
    font-size: 15px;
    font-weight: bold;
}}
QPushButton#PrimaryButton:hover {{
    background-color: #7c3aed;
}}
QPushButton#PrimaryButton:disabled {{
    background-color: {COLORS['surface']};
    color: {COLORS['text_dim']};
}}
/* Secondary buttons */
QPushButton {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 6px 14px;
}}
QPushButton:hover {{
    border-color: {COLORS['magenta']};
}}
QPushButton:disabled {{
    color: {COLORS['text_dim']};
}}
/* Inputs */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 6px 8px;
    color: {COLORS['text']};
    selection-background-color: {COLORS['magenta']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {COLORS['magenta']};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['magenta']};
}}
/* Checkboxes */
QCheckBox {{
    spacing: 8px;
    color: {COLORS['text']};
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {COLORS['border']};
    border-radius: 3px;
    background: {COLORS['surface']};
}}
QCheckBox::indicator:checked {{
    background-color: {COLORS['magenta']};
    border-color: {COLORS['magenta']};
}}
/* Tables */
QTableWidget, QTreeView, QTreeWidget {{
    background-color: {COLORS['bg_alt']};
    alternate-background-color: {COLORS['surface']};
    gridline-color: {COLORS['border']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['magenta']};
}}
QHeaderView::section {{
    background-color: {COLORS['surface']};
    color: {COLORS['text_dim']};
    border: none;
    padding: 6px;
    border-right: 1px solid {COLORS['border']};
}}
/* Progress bar */
QProgressBar {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    text-align: center;
    color: {COLORS['text']};
    height: 22px;
}}
QProgressBar::chunk {{
    background-color: {COLORS['magenta']};
    border-radius: 3px;
}}
/* Tabs */
QTabWidget::pane {{
    border: 1px solid {COLORS['border']};
    background: {COLORS['bg']};
}}
QTabBar::tab {{
    background: {COLORS['bg_alt']};
    color: {COLORS['text_dim']};
    padding: 8px 16px;
    border: 1px solid {COLORS['border']};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{
    background: {COLORS['magenta']};
    color: white;
}}
/* Scrollbars */
QScrollBar:vertical {{
    background: {COLORS['bg_alt']};
    width: 10px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['surface']};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLORS['border']};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0px;
}}
QStatusBar {{
    background-color: {COLORS['bg_alt']};
    color: {COLORS['text_dim']};
    border-top: 1px solid {COLORS['border']};
}}
QGroupBox {{
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 12px;
    color: {COLORS['magenta_lt']};
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}}
"""


def apply_theme(app) -> None:
    """Apply the LeXKit dark stylesheet to a QApplication."""
    app.setStyleSheet(QSS)
