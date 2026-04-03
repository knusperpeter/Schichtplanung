"""Zentrale Farb- und Stylesheet-Definitionen."""
from PySide6.QtGui import QColor

# Schicht-Farbschema
SHIFT_BG: dict[str, str] = {
    "F": "#2980B9",   # Blau   – Frühschicht
    "Z": "#1E8449",   # Grün   – Zwischenschicht
    "S": "#CA6F1E",   # Orange – Spätschicht
    "N": "#1C2833",   # Navy   – Nachtschicht
    "":  "#EDF2F7",   # Hellgrau – Frei
}

SHIFT_FG: dict[str, str] = {
    "F": "#FFFFFF",
    "Z": "#FFFFFF",
    "S": "#FFFFFF",
    "N": "#FFFFFF",
    "":  "#475569",   # auf #EDF2F7: 6.8:1 – deutlich sichtbares Grau für "–"
}

SHIFT_LABEL: dict[str, str] = {
    "F": "Frühschicht  (06:00 – 14:30)",
    "Z": "Zwischenschicht  (10:15 – 18:45)",
    "S": "Spätschicht  (14:00 – 22:30)",
    "N": "Nachtschicht  (22:00 – 06:30)",
    "":  "Frei",
}

# Textfarben für Skill-Level auf hellem Hintergrund (≥ 4.5:1 Kontrast)
SKILL_COLOR: dict[str, str] = {
    "EXPERT":   "#166534",   # dunkles Grün   – auf Weiß 7.1:1
    "MEDIUM":   "#7C4D00",   # dunkles Braun  – auf Weiß 7.0:1
    "BEGINNER": "#991B1B",   # dunkles Rot    – auf Weiß 6.9:1
}

SKILL_LABEL: dict[str, str] = {
    "EXPERT":   "Erfahren",
    "MEDIUM":   "Mittel",
    "BEGINNER": "Anfänger",
}

CONTRACT_LABEL: dict[str, str] = {
    "FULLTIME_40": "Vollzeit 40h",
    "MIN_24":      "Min 24h",
    "MAX_20":      "Max 20h",
    "MINIJOB":     "Minijob",
}

OCCUPANCY_COLOR: dict[str, str] = {
    "LOW":    "#166534",   # dunkles Grün
    "MEDIUM": "#7C4D00",   # dunkles Braun
    "HIGH":   "#991B1B",   # dunkles Rot
}

# Dedizierte Textfarben für Legende (auf weißem / hellem Hintergrund)
SHIFT_TEXT_COLOR: dict[str, str] = {
    "F": "#1A5D9E",   # dunkles Blau  – auf Weiß 5.8:1
    "Z": "#155D27",   # dunkles Grün  – auf Weiß 7.5:1
    "S": "#7C3D00",   # dunkles Orange – auf Weiß 8.2:1
    "N": "#1C2833",   # sehr dunkles Navy – auf Weiß 14:1
}

STATUS_OK      = "#166534"
STATUS_WARN    = "#7C4D00"
STATUS_ERROR   = "#991B1B"

# Wochenend-Spalten Hintergrund (Plan-Grid)
WEEKEND_HEADER_BG = "#FEF3C7"

APP_STYLESHEET = """
/* ── Fenster & Dialoge ─────────────────────────────────────────── */
QMainWindow, QDialog {
    background-color: #F0F4F8;
    font-family: -apple-system, "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    color: #1E293B;
}

/* ── Tabs ──────────────────────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #CBD5E1;
    border-top: none;
    background: #FFFFFF;
}
QTabBar::tab {
    min-width: 160px;
    padding: 9px 48px;
    font-size: 12px;
    font-weight: 500;
    color: #334155;
    background: #E2E8F0;
    border: 1px solid #CBD5E1;
    border-bottom: none;
    margin-right: 2px;
    border-radius: 6px 6px 0 0;
}
QTabBar::tab:selected {
    color: #1E293B;
    background: #FFFFFF;
    font-weight: bold;
    border-bottom: 3px solid #2563EB;
}
QTabBar::tab:hover:!selected {
    background: #EFF6FF;
    color: #1E40AF;
}

/* ── Buttons ───────────────────────────────────────────────────── */
QPushButton {
    padding: 6px 16px;
    border: 1px solid #CBD5E1;
    border-radius: 5px;
    background: #FFFFFF;
    font-size: 12px;
    font-weight: 500;
    color: #374151;
}
QPushButton:hover {
    background: #EFF6FF;
    border-color: #93C5FD;
    color: #1E40AF;
}
QPushButton:pressed {
    background: #DBEAFE;
    border-color: #3B82F6;
}
QPushButton:disabled {
    background: #F1F5F9;
    color: #94A3B8;
    border-color: #E2E8F0;
}
QPushButton#primary {
    background: #2563EB;
    color: #FFFFFF;
    border: none;
    font-weight: bold;
}
QPushButton#primary:hover  { background: #1D4ED8; }
QPushButton#primary:pressed { background: #1E40AF; }

/* ── Tabellen ──────────────────────────────────────────────────── */
QTableWidget {
    gridline-color: #E2E8F0;
    font-size: 12px;
    background: #FFFFFF;
    selection-background-color: #DBEAFE;
    selection-color: #1E293B;
}
QTableWidget QHeaderView::section {
    background: #1E293B;
    color: #FFFFFF;
    padding: 6px 4px;
    border: none;
    border-right: 1px solid #334155;
    border-bottom: 2px solid #334155;
    font-size: 11px;
    font-weight: bold;
}
QTableWidget QHeaderView::section:vertical {
    background: #F8FAFC;
    color: #1E293B;
    border-right: 2px solid #CBD5E1;
    border-bottom: 1px solid #E2E8F0;
}

/* ── Eingabefelder ─────────────────────────────────────────────── */
QLineEdit, QTextEdit {
    padding: 5px 10px;
    border: 1px solid #CBD5E1;
    border-radius: 5px;
    background: #FFFFFF;
    color: #1E293B;
    font-size: 12px;
}
QLineEdit:focus, QTextEdit:focus {
    border-color: #2563EB;
    background: #FAFEFF;
}
QSpinBox, QDateEdit {
    padding: 4px 8px;
    border: 1px solid #CBD5E1;
    border-radius: 5px;
    background: #FFFFFF;
    color: #1E293B;
    font-size: 12px;
}
QSpinBox:focus, QDateEdit:focus {
    border-color: #2563EB;
}
QComboBox {
    padding: 5px 10px;
    border: 1px solid #CBD5E1;
    border-radius: 5px;
    background: #FFFFFF;
    color: #1E293B;
    font-size: 12px;
}
QComboBox:hover  { border-color: #93C5FD; }
QComboBox:focus  { border-color: #2563EB; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #FFFFFF;
    border: 1px solid #CBD5E1;
    selection-background-color: #DBEAFE;
    selection-color: #1E293B;
}

/* ── Labels ────────────────────────────────────────────────────── */
QLabel#section-title {
    font-size: 16px;
    font-weight: bold;
    color: #1E293B;
    padding: 4px 0;
}
QLabel#info {
    color: #64748B;
    font-size: 12px;
}

/* ── Scrollbars (schlank) ──────────────────────────────────────── */
QScrollBar:vertical {
    background: #F1F5F9;
    width: 7px;
    border-radius: 4px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #CBD5E1;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #94A3B8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #F1F5F9;
    height: 7px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #CBD5E1;
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover { background: #94A3B8; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Splitter ──────────────────────────────────────────────────── */
QSplitter::handle {
    background: #E2E8F0;
    width: 3px;
    height: 3px;
}
QSplitter::handle:hover { background: #93C5FD; }

/* ── Menüleiste ────────────────────────────────────────────────── */
QMenuBar {
    background: #1E293B;
    color: #E2E8F0;
    font-size: 12px;
    padding: 2px;
}
QMenuBar::item {
    padding: 5px 12px;
    background: transparent;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background: #334155;
    color: #FFFFFF;
}
QMenu {
    background: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 7px 22px;
    color: #1E293B;
    border-radius: 4px;
    font-size: 12px;
}
QMenu::item:selected {
    background: #EFF6FF;
    color: #1E40AF;
}
QMenu::separator {
    height: 1px;
    background: #E2E8F0;
    margin: 4px 8px;
}
"""

DARK_STYLESHEET = """
/* ── Fenster & Dialoge ─────────────────────────────────────────── */
QMainWindow, QDialog, QWidget {
    background-color: #0F172A;
    font-family: -apple-system, "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    color: #F1F5F9;
}

/* ── Tabs ──────────────────────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #334155;
    border-top: none;
    background: #1E293B;
}
QTabBar::tab {
    min-width: 160px;
    padding: 9px 48px;
    font-size: 12px;
    font-weight: 500;
    color: #94A3B8;
    background: #0F172A;
    border: 1px solid #334155;
    border-bottom: none;
    margin-right: 2px;
    border-radius: 6px 6px 0 0;
}
QTabBar::tab:selected {
    color: #F1F5F9;
    background: #1E293B;
    font-weight: bold;
    border-bottom: 3px solid #3B82F6;
}
QTabBar::tab:hover:!selected {
    background: #1E293B;
    color: #CBD5E1;
}

/* ── Buttons ───────────────────────────────────────────────────── */
QPushButton {
    padding: 6px 16px;
    border: 1px solid #334155;
    border-radius: 5px;
    background: #1E293B;
    font-size: 12px;
    font-weight: 500;
    color: #F1F5F9;
}
QPushButton:hover {
    background: #334155;
    border-color: #475569;
    color: #FFFFFF;
}
QPushButton:pressed { background: #475569; }
QPushButton:disabled {
    background: #1E293B;
    color: #475569;
    border-color: #334155;
}
QPushButton#primary {
    background: #2563EB;
    color: #FFFFFF;
    border: none;
    font-weight: bold;
}
QPushButton#primary:hover  { background: #1D4ED8; }
QPushButton#primary:pressed { background: #1E40AF; }

/* ── Tabellen ──────────────────────────────────────────────────── */
QTableWidget {
    gridline-color: #334155;
    font-size: 12px;
    background: #1E293B;
    color: #F1F5F9;
    selection-background-color: #1D4ED8;
    selection-color: #FFFFFF;
}
QTableWidget::item { color: #F1F5F9; background: #1E293B; }
QTableWidget QHeaderView::section {
    background: #0F172A;
    color: #F1F5F9;
    padding: 6px 4px;
    border: none;
    border-right: 1px solid #334155;
    border-bottom: 2px solid #334155;
    font-size: 11px;
    font-weight: bold;
}
QTableWidget QHeaderView::section:vertical {
    background: #1E293B;
    color: #F1F5F9;
    border-right: 2px solid #334155;
    border-bottom: 1px solid #334155;
}

/* ── Eingabefelder ─────────────────────────────────────────────── */
QLineEdit, QTextEdit {
    padding: 5px 10px;
    border: 1px solid #334155;
    border-radius: 5px;
    background: #1E293B;
    color: #F1F5F9;
    font-size: 12px;
}
QLineEdit:focus, QTextEdit:focus { border-color: #3B82F6; }
QSpinBox, QDateEdit, QDoubleSpinBox {
    padding: 4px 8px;
    border: 1px solid #334155;
    border-radius: 5px;
    background: #1E293B;
    color: #F1F5F9;
    font-size: 12px;
}
QSpinBox:focus, QDateEdit:focus { border-color: #3B82F6; }
QComboBox {
    padding: 5px 10px;
    border: 1px solid #334155;
    border-radius: 5px;
    background: #1E293B;
    color: #F1F5F9;
    font-size: 12px;
}
QComboBox:hover  { border-color: #475569; }
QComboBox:focus  { border-color: #3B82F6; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #1E293B;
    border: 1px solid #334155;
    color: #F1F5F9;
    selection-background-color: #1D4ED8;
    selection-color: #FFFFFF;
}

/* ── Labels ────────────────────────────────────────────────────── */
QLabel { color: #F1F5F9; }
QLabel#section-title { font-size: 16px; font-weight: bold; color: #F1F5F9; padding: 4px 0; }
QLabel#info { color: #94A3B8; font-size: 12px; }

/* ── Scrollbars ────────────────────────────────────────────────── */
QScrollBar:vertical { background: #1E293B; width: 7px; border-radius: 4px; margin: 0; }
QScrollBar::handle:vertical { background: #475569; border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #64748B; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #1E293B; height: 7px; border-radius: 4px; }
QScrollBar::handle:horizontal { background: #475569; border-radius: 4px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: #64748B; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Splitter ──────────────────────────────────────────────────── */
QSplitter::handle { background: #334155; width: 3px; height: 3px; }
QSplitter::handle:hover { background: #475569; }

/* ── Menüleiste ────────────────────────────────────────────────── */
QMenuBar { background: #0F172A; color: #F1F5F9; font-size: 12px; padding: 2px; }
QMenuBar::item { padding: 5px 12px; background: transparent; border-radius: 4px; }
QMenuBar::item:selected { background: #1E293B; color: #FFFFFF; }
QMenu { background: #1E293B; border: 1px solid #334155; border-radius: 6px; padding: 4px; }
QMenu::item { padding: 7px 22px; color: #F1F5F9; border-radius: 4px; font-size: 12px; }
QMenu::item:selected { background: #334155; color: #FFFFFF; }
QMenu::separator { height: 1px; background: #334155; margin: 4px 8px; }

/* ── Listen ────────────────────────────────────────────────────── */
QListWidget {
    background: #1E293B;
    color: #F1F5F9;
    border: 1px solid #334155;
    border-radius: 4px;
}
QListWidget::item { padding: 6px 10px; color: #F1F5F9; }
QListWidget::item:selected { background: #1D4ED8; color: #FFFFFF; }

/* ── Frames ────────────────────────────────────────────────────── */
QFrame { background: #1E293B; }
"""
