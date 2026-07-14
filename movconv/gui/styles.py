"""A single modern dark stylesheet (QSS) for the whole application."""

# Colour palette
BG = "#12141a"
SURFACE = "#1b1e27"
SURFACE_2 = "#232733"
BORDER = "#2e3340"
TEXT = "#e6e9ef"
TEXT_DIM = "#9aa3b2"
ACCENT = "#4f8cff"
ACCENT_HOVER = "#6ba0ff"
ACCENT_PRESSED = "#3d76e0"
DANGER = "#e5484d"
SUCCESS = "#46b17b"


STYLESHEET = f"""
* {{
    font-family: "Segoe UI", "SF Pro Text", "Ubuntu", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QWidget#Root {{
    background: {BG};
}}
QLabel#Title {{
    font-size: 20px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#Subtitle {{
    color: {TEXT_DIM};
}}
QLabel[dim="true"] {{
    color: {TEXT_DIM};
}}

/* Drag & drop zone */
QFrame#DropArea {{
    background: {SURFACE};
    border: 2px dashed {BORDER};
    border-radius: 14px;
}}
QFrame#DropArea[dragActive="true"] {{
    border-color: {ACCENT};
    background: {SURFACE_2};
}}
QLabel#DropHeadline {{
    color: {TEXT};
    font-size: 15px;
    font-weight: 600;
}}
QLabel#DropHint {{
    color: {TEXT_DIM};
    font-size: 12px;
}}

/* Cards / group boxes */
QGroupBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    margin-top: 12px;
    padding: 8px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: {TEXT_DIM};
    font-weight: 600;
}}

/* Table */
QTableWidget {{
    background: {SURFACE};
    alternate-background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 10px;
    selection-background-color: rgba(79,140,255,0.28);
    selection-color: {TEXT};
    outline: none;
}}
QHeaderView::section {{
    background: {SURFACE_2};
    color: {TEXT_DIM};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px 10px;
    font-weight: 600;
}}
QTableWidget::item {{
    padding: 4px 10px;
    border: none;
}}

/* Buttons */
QPushButton {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 14px;
    color: {TEXT};
}}
QPushButton:hover {{
    border-color: {ACCENT};
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    background: {SURFACE};
}}
QPushButton#Primary {{
    background: {ACCENT};
    border: none;
    color: white;
    font-weight: 600;
}}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#Primary:pressed {{ background: {ACCENT_PRESSED}; }}
QPushButton#Primary:disabled {{ background: {SURFACE_2}; color: {TEXT_DIM}; }}
QPushButton#Danger {{
    background: transparent;
    border: 1px solid {DANGER};
    color: {DANGER};
}}
QPushButton#Danger:hover {{ background: rgba(229,72,77,0.12); }}

/* Inputs */
QComboBox, QLineEdit {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 10px;
}}
QComboBox:hover, QLineEdit:focus {{
    border-color: {ACCENT};
}}
QComboBox QAbstractItemView {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    selection-color: white;
    outline: none;
}}
QCheckBox {{ spacing: 8px; }}

/* Progress bars */
QProgressBar {{
    background: {SURFACE_2};
    border: none;
    border-radius: 7px;
    height: 14px;
    text-align: center;
    color: {TEXT};
    font-size: 11px;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 7px;
}}
QProgressBar[state="done"]::chunk {{ background: {SUCCESS}; }}
QProgressBar[state="failed"]::chunk {{ background: {DANGER}; }}

/* Log console */
QPlainTextEdit#Log {{
    background: #0d0f14;
    border: 1px solid {BORDER};
    border-radius: 10px;
    color: {TEXT_DIM};
    font-family: "Cascadia Code", "Consolas", "Menlo", monospace;
    font-size: 12px;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {TEXT_DIM}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""
