"""
ShiftButton – die einzelne Schicht-Zelle im Planungsgrid.

Klick öffnet ein Kontextmenü zum Wechsel des Schichttyps.
Schichten ohne Zuweisung werden als "–" angezeigt.
Manuelle Überschreibungen werden mit einem * markiert.
"""
from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtGui import QCursor, QAction
from PySide6.QtWidgets import QPushButton, QMenu, QSizePolicy

from src.ui.styles import SHIFT_BG, SHIFT_FG, SHIFT_LABEL


class ShiftButton(QPushButton):
    """
    Klickbarer Button für eine Schicht-Zelle (Mitarbeiter × Tag).

    Signals:
        shift_changed(emp_id, day, shift_type):
            Wird ausgelöst wenn der Nutzer die Schicht ändert.
            shift_type ist "" für "frei".
    """

    shift_changed = Signal(int, object, str)   # emp_id, date, shift_type

    def __init__(
        self,
        shift_type: str,
        emp_id: int,
        day: date,
        is_manual: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.emp_id = emp_id
        self.day = day
        self._shift = shift_type
        self._is_manual = is_manual

        self.setFlat(True)
        self.setCursor(QCursor())
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._apply_style()
        self.clicked.connect(self._show_menu)

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    @property
    def shift_type(self) -> str:
        return self._shift

    def set_shift(self, shift_type: str, is_manual: bool = True) -> None:
        """Schicht programmatisch setzen (ohne DB-Schreiben)."""
        self._shift = shift_type
        self._is_manual = is_manual
        self._apply_style()

    # ------------------------------------------------------------------
    # Privat
    # ------------------------------------------------------------------

    def _apply_style(self) -> None:
        bg = SHIFT_BG.get(self._shift, SHIFT_BG[""])
        fg = SHIFT_FG.get(self._shift, SHIFT_FG[""])
        label = self._shift if self._shift else "–"
        if self._is_manual and self._shift:
            label += "*"
        self.setText(label)
        self.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {bg};"
            f"  color: {fg};"
            f"  border: none;"
            f"  font-weight: bold;"
            f"  font-size: 12px;"
            f"  border-radius: 0;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {self._darken(bg)};"
            f"}}"
        )

    @staticmethod
    def _darken(hex_color: str, factor: float = 0.85) -> str:
        """Verdunkelt eine Hex-Farbe leicht für Hover-Effekt."""
        c = hex_color.lstrip("#")
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        r, g, b = (int(x * factor) for x in (r, g, b))
        return f"#{r:02X}{g:02X}{b:02X}"

    def _show_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { font-size: 12px; } QMenu::item { padding: 6px 20px; }")

        for code, label in SHIFT_LABEL.items():
            action = QAction(label, self)
            if code == self._shift:
                action.setCheckable(True)
                action.setChecked(True)
            action.setData(code)
            menu.addAction(action)

        chosen = menu.exec(self.mapToGlobal(self.rect().bottomLeft()))
        if chosen and chosen.data() != self._shift:
            new_shift = chosen.data()
            self.set_shift(new_shift, is_manual=True)
            self.shift_changed.emit(self.emp_id, self.day, new_shift)
