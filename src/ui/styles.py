"""
Zentrale Design-Token und Stylesheet-Definitionen.

Farbsystem nach shadcn/ui (zinc-Palette, oklch → hex übersetzt):

  Light                   Dark
  BG      #FAFAFA         #09090B   (zinc-50 / zinc-950)
  CARD    #FFFFFF         #18181B   (white  / zinc-900)
  MUTED   #F4F4F5         #27272A   (zinc-100 / zinc-800)
  BORDER  #E4E4E7         #3F3F46   (zinc-200 / zinc-700)
  FG      #09090B         #FAFAFA   (zinc-950 / zinc-50)
  MUTED_FG#71717A         #A1A1AA   (zinc-500 / zinc-400)
  PRIMARY #18181B / white fg         (zinc-900 – shadcn Standard)
"""
from PySide6.QtGui import QColor  # noqa: F401  (für Aufrufer)

# ── Schicht-Farbschema (muted badge-Stil, shadcn-inspiriert) ─────────────
# Hintergrundfarben für Plan-Zellen
SHIFT_BG: dict[str, str] = {
    "F": "#DBEAFE",   # blue-100  – Frühschicht
    "Z": "#D1FAE5",   # emerald-100 – Zwischenschicht
    "S": "#FFEDD5",   # orange-100 – Spätschicht
    "N": "#EDE9FE",   # violet-100 – Nachtschicht
    "":  "#F4F4F5",   # zinc-100   – Frei
}

SHIFT_FG: dict[str, str] = {
    "F": "#1E40AF",   # blue-800    auf blue-100   5.8:1 ✓
    "Z": "#065F46",   # emerald-800 auf emerald-100 7.3:1 ✓
    "S": "#9A3412",   # orange-800  auf orange-100  6.2:1 ✓
    "N": "#4C1D95",   # violet-900  auf violet-100  8.1:1 ✓
    "":  "#52525B",   # zinc-600    auf zinc-100    6.1:1 ✓
}

SHIFT_LABEL: dict[str, str] = {
    "F": "Frühschicht  (06:00 – 14:30)",
    "Z": "Zwischenschicht  (10:15 – 18:45)",
    "S": "Spätschicht  (14:00 – 22:30)",
    "N": "Nachtschicht  (22:00 – 06:30)",
    "":  "Frei",
}

# ── Skill- / Auslastungs-Farben (auf hellem Hintergrund ≥ 4.5:1) ─────────
SKILL_COLOR: dict[str, str] = {
    "EXPERT":   "#15803D",   # green-700   7.1:1 auf Weiß ✓
    "MEDIUM":   "#B45309",   # amber-700   4.7:1 auf Weiß ✓
    "BEGINNER": "#B91C1C",   # red-700     5.1:1 auf Weiß ✓
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
    "LOW":    "#15803D",   # green-700
    "MEDIUM": "#B45309",   # amber-700
    "HIGH":   "#B91C1C",   # red-700
}

# Legende – Textfarben auf weißem Hintergrund
SHIFT_TEXT_COLOR: dict[str, str] = {
    "F": "#1E40AF",
    "Z": "#065F46",
    "S": "#9A3412",
    "N": "#4C1D95",
}

# Statusfarben (Hintergrund der ValidationBar UND Textfarbe in Dialogen)
STATUS_OK    = "#15803D"   # green-700
STATUS_WARN  = "#B45309"   # amber-700
STATUS_ERROR = "#B91C1C"   # red-700

# Wochenend-Spalten-Hintergrund (Plan-Grid)
WEEKEND_HEADER_BG = "#FEF9C3"   # yellow-100

# ── Licht-Theme (shadcn/ui Zinc) ─────────────────────────────────────────
APP_STYLESHEET = """
/* ── Fenster & Basis ────────────────────────────────────────────── */
QMainWindow, QDialog, QWidget {
    background-color: #FAFAFA;
    font-family: -apple-system, "Segoe UI", "Inter", Arial, sans-serif;
    font-size: 13px;
    color: #09090B;
}

/* ── Tab-Widget (shadcn default "pill / segment" Stil) ──────────── */
/*
   TabsList  → QTabBar  background #F4F4F5, rounded-lg, padding 3px
   TabsTrigger aktiv   → bg-background (#FFFFFF), border 1px #E4E4E7
   TabsTrigger inaktiv → transparent, text foreground/60 (#71717A)
*/
QTabWidget {
    background: #FAFAFA;
}
QTabWidget::pane {
    border: none;
    background: #FFFFFF;
}

QTabBar {
    background: transparent;
    qproperty-drawBase: 0;
}

/* Die ganze TabsList-Leiste als pill-Container */
QTabWidget > QTabBar {
    background: transparent;
}

QTabBar::tab {
    min-width: 130px;
    padding: 6px 20px;
    font-size: 13px;
    font-weight: 500;
    color: #71717A;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    margin: 3px 2px;
}
QTabBar::tab:hover:!selected {
    color: #3F3F46;
    background: rgba(255, 255, 255, 0.8);
    border-color: #E4E4E7;
}
QTabBar::tab:selected {
    color: #09090B;
    background: #FFFFFF;
    font-weight: 600;
    border: 1px solid #E4E4E7;
}
QTabBar::tab:disabled {
    color: #A1A1AA;
    opacity: 0.5;
}

/* ── Buttons ────────────────────────────────────────────────────── */
QPushButton {
    padding: 7px 16px;
    border: 1px solid #E4E4E7;
    border-radius: 6px;
    background: #FFFFFF;
    font-size: 12px;
    font-weight: 500;
    color: #09090B;
}
QPushButton:hover {
    background: #F4F4F5;
    border-color: #D4D4D8;
}
QPushButton:pressed {
    background: #E4E4E7;
    border-color: #A1A1AA;
}
QPushButton:disabled {
    background: #F4F4F5;
    color: #A1A1AA;
    border-color: #E4E4E7;
}
QPushButton#primary {
    background: #18181B;
    color: #FAFAFA;
    border: none;
    font-weight: 600;
}
QPushButton#primary:hover  { background: #27272A; }
QPushButton#primary:pressed { background: #3F3F46; }

/* ── Tabellen (shadcn/ui Table-Stil) ────────────────────────────── */
QTableWidget {
    gridline-color: transparent;
    font-size: 13px;
    background: #FFFFFF;
    selection-background-color: #F4F4F5;
    selection-color: #09090B;
    border: none;
    outline: none;
}
QTableWidget::item {
    padding: 12px 16px;
    border-bottom: 1px solid #E4E4E7;
    color: #09090B;
}
QTableWidget::item:hover {
    background: #F4F4F5;
}
QTableWidget::item:selected {
    background: #F4F4F5;
    color: #09090B;
}
QTableWidget QHeaderView {
    border: none;
    background: transparent;
}
QTableWidget QHeaderView::section {
    background: transparent;
    color: #71717A;
    padding: 10px 16px;
    height: 40px;
    border: none;
    border-bottom: 1px solid #E4E4E7;
    font-size: 12px;
    font-weight: 500;
}
QTableWidget QHeaderView::section:vertical {
    background: transparent;
    color: #71717A;
    padding: 10px 8px;
    border: none;
    border-bottom: 1px solid #E4E4E7;
    font-weight: 500;
}

/* ── Eingabefelder ──────────────────────────────────────────────── */
QLineEdit, QTextEdit {
    padding: 6px 10px;
    border: 1px solid #E4E4E7;
    border-radius: 6px;
    background: #FFFFFF;
    color: #09090B;
    font-size: 12px;
}
QLineEdit:focus, QTextEdit:focus {
    border-color: #A1A1AA;
}
QSpinBox, QDateEdit, QDoubleSpinBox {
    padding: 0px 8px;
    border: 1px solid #E4E4E7;
    border-radius: 6px;
    background: #FFFFFF;
    color: #09090B;
    font-size: 13px;
    min-height: 0px;
}
QSpinBox:focus, QDateEdit:focus, QDoubleSpinBox:focus {
    border-color: #A1A1AA;
}
QComboBox {
    padding: 6px 10px;
    border: 1px solid #E4E4E7;
    border-radius: 6px;
    background: #FFFFFF;
    color: #09090B;
    font-size: 12px;
}
QComboBox:hover  { border-color: #D4D4D8; }
QComboBox:focus  { border-color: #A1A1AA; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #FFFFFF;
    border: 1px solid #E4E4E7;
    border-radius: 6px;
    selection-background-color: #F4F4F5;
    selection-color: #09090B;
    outline: none;
}

/* ── Labels ─────────────────────────────────────────────────────── */
QLabel#section-title {
    font-size: 16px;
    font-weight: 700;
    color: #09090B;
    padding: 4px 0;
    letter-spacing: -0.3px;
}
QLabel#info {
    color: #71717A;
    font-size: 12px;
}

/* ── Listen ─────────────────────────────────────────────────────── */
QListWidget {
    background: #FFFFFF;
    border: 1px solid #E4E4E7;
    border-radius: 6px;
    outline: none;
    font-size: 12px;
}
QListWidget::item { padding: 7px 10px; color: #09090B; }
QListWidget::item:selected {
    background: #18181B;
    color: #FAFAFA;
    border-radius: 4px;
}
QListWidget::item:hover:!selected { background: #F4F4F5; }

/* ── Frames / Cards ─────────────────────────────────────────────── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    border: 1px solid #E4E4E7;
    border-radius: 8px;
    background: #FFFFFF;
}

/* ── Scrollbars (ultra-schlank) ─────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    border-radius: 3px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #D4D4D8;
    border-radius: 3px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #A1A1AA; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: transparent;
    height: 6px;
    border-radius: 3px;
}
QScrollBar::handle:horizontal {
    background: #D4D4D8;
    border-radius: 3px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover { background: #A1A1AA; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Splitter ───────────────────────────────────────────────────── */
QSplitter::handle {
    background: #E4E4E7;
    width: 1px;
    height: 1px;
}
QSplitter::handle:hover { background: #A1A1AA; }

/* ── Menüleiste ─────────────────────────────────────────────────── */
QMenuBar {
    background: #18181B;
    color: #F4F4F5;
    font-size: 12px;
    padding: 2px;
}
QMenuBar::item {
    padding: 6px 12px;
    background: transparent;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background: #27272A;
    color: #FFFFFF;
}
QMenu {
    background: #FFFFFF;
    border: 1px solid #E4E4E7;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 7px 22px;
    color: #09090B;
    border-radius: 4px;
    font-size: 12px;
}
QMenu::item:selected {
    background: #F4F4F5;
    color: #09090B;
}
QMenu::separator {
    height: 1px;
    background: #E4E4E7;
    margin: 4px 8px;
}

/* ── ToolTips ───────────────────────────────────────────────────── */
QToolTip {
    background: #18181B;
    color: #FAFAFA;
    border: none;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
}
"""

# ── Dunkel-Theme (shadcn/ui Zinc Dark) ───────────────────────────────────
DARK_STYLESHEET = """
/* ── Fenster & Basis ────────────────────────────────────────────── */
QMainWindow, QDialog, QWidget {
    background-color: #09090B;
    font-family: -apple-system, "Segoe UI", "Inter", Arial, sans-serif;
    font-size: 13px;
    color: #FAFAFA;
}

/* ── Tab-Widget (shadcn default "pill / segment" Stil – Dark) ───── */
QTabWidget {
    background: #09090B;
}
QTabWidget::pane {
    border: none;
    background: #18181B;
}

QTabBar {
    background: transparent;
    qproperty-drawBase: 0;
}

QTabBar::tab {
    min-width: 130px;
    padding: 6px 20px;
    font-size: 13px;
    font-weight: 500;
    color: #A1A1AA;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    margin: 3px 2px;
}
QTabBar::tab:hover:!selected {
    color: #D4D4D8;
    background: rgba(255, 255, 255, 0.06);
    border-color: #3F3F46;
}
QTabBar::tab:selected {
    color: #FAFAFA;
    background: #27272A;
    font-weight: 600;
    border: 1px solid #3F3F46;
}
QTabBar::tab:disabled {
    color: #52525B;
}

/* ── Buttons ────────────────────────────────────────────────────── */
QPushButton {
    padding: 7px 16px;
    border: 1px solid #3F3F46;
    border-radius: 6px;
    background: #18181B;
    font-size: 12px;
    font-weight: 500;
    color: #FAFAFA;
}
QPushButton:hover {
    background: #27272A;
    border-color: #52525B;
}
QPushButton:pressed { background: #3F3F46; }
QPushButton:disabled {
    background: #18181B;
    color: #52525B;
    border-color: #27272A;
}
QPushButton#primary {
    background: #E4E4E7;
    color: #18181B;
    border: none;
    font-weight: 600;
}
QPushButton#primary:hover  { background: #F4F4F5; }
QPushButton#primary:pressed { background: #D4D4D8; }

/* ── Tabellen (shadcn/ui Table-Stil – Dark) ─────────────────────── */
QTableWidget {
    gridline-color: transparent;
    font-size: 13px;
    background: #18181B;
    color: #FAFAFA;
    selection-background-color: #27272A;
    selection-color: #FAFAFA;
    border: none;
    outline: none;
}
QTableWidget::item {
    padding: 12px 16px;
    border-bottom: 1px solid #27272A;
    color: #FAFAFA;
}
QTableWidget::item:hover {
    background: #27272A;
}
QTableWidget::item:selected {
    background: #27272A;
    color: #FAFAFA;
}
QTableWidget QHeaderView {
    border: none;
    background: transparent;
}
QTableWidget QHeaderView::section {
    background: transparent;
    color: #A1A1AA;
    padding: 10px 16px;
    height: 40px;
    border: none;
    border-bottom: 1px solid #27272A;
    font-size: 12px;
    font-weight: 500;
}
QTableWidget QHeaderView::section:vertical {
    background: transparent;
    color: #A1A1AA;
    padding: 10px 8px;
    border: none;
    border-bottom: 1px solid #27272A;
    font-weight: 500;
}

/* ── Eingabefelder ──────────────────────────────────────────────── */
QLineEdit, QTextEdit {
    padding: 6px 10px;
    border: 1px solid #3F3F46;
    border-radius: 6px;
    background: #18181B;
    color: #FAFAFA;
    font-size: 12px;
}
QLineEdit:focus, QTextEdit:focus { border-color: #71717A; }
QSpinBox, QDateEdit, QDoubleSpinBox {
    padding: 0px 8px;
    border: 1px solid #3F3F46;
    border-radius: 6px;
    background: #18181B;
    color: #FAFAFA;
    font-size: 13px;
    min-height: 0px;
}
QSpinBox:focus, QDateEdit:focus, QDoubleSpinBox:focus { border-color: #71717A; }
QComboBox {
    padding: 6px 10px;
    border: 1px solid #3F3F46;
    border-radius: 6px;
    background: #18181B;
    color: #FAFAFA;
    font-size: 12px;
}
QComboBox:hover  { border-color: #52525B; }
QComboBox:focus  { border-color: #71717A; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #18181B;
    border: 1px solid #3F3F46;
    border-radius: 6px;
    color: #FAFAFA;
    selection-background-color: #27272A;
    selection-color: #FAFAFA;
    outline: none;
}

/* ── Labels ─────────────────────────────────────────────────────── */
QLabel { color: #FAFAFA; }
QLabel#section-title {
    font-size: 16px;
    font-weight: 700;
    color: #FAFAFA;
    padding: 4px 0;
    letter-spacing: -0.3px;
}
QLabel#info { color: #A1A1AA; font-size: 12px; }

/* ── Listen ─────────────────────────────────────────────────────── */
QListWidget {
    background: #18181B;
    color: #FAFAFA;
    border: 1px solid #3F3F46;
    border-radius: 6px;
    outline: none;
    font-size: 12px;
}
QListWidget::item { padding: 7px 10px; color: #FAFAFA; }
QListWidget::item:selected {
    background: #E4E4E7;
    color: #09090B;
    border-radius: 4px;
}
QListWidget::item:hover:!selected { background: #27272A; }

/* ── Frames / Cards ─────────────────────────────────────────────── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    border: 1px solid #3F3F46;
    border-radius: 8px;
    background: #18181B;
}

/* ── Scrollbars ─────────────────────────────────────────────────── */
QScrollBar:vertical { background: transparent; width: 6px; border-radius: 3px; margin: 0; }
QScrollBar::handle:vertical { background: #3F3F46; border-radius: 3px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #52525B; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 6px; border-radius: 3px; }
QScrollBar::handle:horizontal { background: #3F3F46; border-radius: 3px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: #52525B; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Splitter ───────────────────────────────────────────────────── */
QSplitter::handle { background: #27272A; width: 1px; height: 1px; }
QSplitter::handle:hover { background: #52525B; }

/* ── Menüleiste ─────────────────────────────────────────────────── */
QMenuBar { background: #09090B; color: #F4F4F5; font-size: 12px; padding: 2px; }
QMenuBar::item { padding: 6px 12px; background: transparent; border-radius: 4px; }
QMenuBar::item:selected { background: #18181B; color: #FFFFFF; }
QMenu {
    background: #18181B;
    border: 1px solid #3F3F46;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item { padding: 7px 22px; color: #FAFAFA; border-radius: 4px; font-size: 12px; }
QMenu::item:selected { background: #27272A; color: #FAFAFA; }
QMenu::separator { height: 1px; background: #27272A; margin: 4px 8px; }

/* ── ToolTips ───────────────────────────────────────────────────── */
QToolTip {
    background: #27272A;
    color: #FAFAFA;
    border: 1px solid #3F3F46;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
}
"""
