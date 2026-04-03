"""
ValidationBar – untere Statusleiste mit Echtzeit-Validierungsergebnissen.

Zeigt:
  ✓  Kein Verstoß          (grün)
  ⚠  N Warnungen           (gelb)
  ✕  N Verstöße            (rot)

Klick auf die Leiste klappt eine Detailansicht aus.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea,
)

from src.ui.styles import STATUS_OK, STATUS_WARN, STATUS_ERROR


class ValidationBar(QWidget):

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._violations: list[str] = []
        self._warnings: list[str] = []
        self._detail_visible = False
        self._dark_mode = False
        self._setup_ui()
        self.show_ok()

    def set_dark_mode(self, dark: bool) -> None:
        self._dark_mode = dark
        self._detail_frame.setStyleSheet(
            "background: #1E293B; border-top: 1px solid #334155;"
            if dark else
            "background: #FAFAFA; border-top: 1px solid #CBD5E1;"
        )
        self._detail_content.setStyleSheet(
            "font-size: 11px; color: #F1F5F9; line-height: 1.6;"
            if dark else
            "font-size: 11px; color: #1E293B; line-height: 1.6;"
        )
        if self._violations or self._warnings:
            self._rebuild_detail()

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    def show_ok(self) -> None:
        self._violations = []
        self._warnings = []
        self._update_bar(STATUS_OK, "✓  Kein Verstoß – Plan ist arbeitsrechtlich korrekt.")

    def show_violations(self, violations: list[str], warnings: list[str] | None = None) -> None:
        self._violations = violations
        self._warnings = warnings or []
        if violations:
            msg = f"✕  {len(violations)} Verstoß{'e' if len(violations) > 1 else ''}"
            if self._warnings:
                msg += f"  ·  ⚠ {len(self._warnings)} Hinweis{'e' if len(self._warnings) > 1 else ''}"
            self._update_bar(STATUS_ERROR, msg)
        elif self._warnings:
            self._update_bar(STATUS_WARN, f"⚠  {len(self._warnings)} Hinweis{'e' if len(self._warnings) > 1 else ''}")
        else:
            self.show_ok()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Hauptleiste
        self._bar = QFrame()
        self._bar.setFixedHeight(34)
        bar_layout = QHBoxLayout(self._bar)
        bar_layout.setContentsMargins(12, 0, 12, 0)

        self._status_label = QLabel()
        self._status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: white;")
        bar_layout.addWidget(self._status_label)
        bar_layout.addStretch()

        self._toggle_btn = QPushButton("Details ▾")
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setStyleSheet("color: white; font-size: 11px; border: none;")
        self._toggle_btn.clicked.connect(self._toggle_detail)
        bar_layout.addWidget(self._toggle_btn)

        outer.addWidget(self._bar)

        # Detailbereich
        self._detail_frame = QFrame()
        self._detail_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._detail_frame.setMaximumHeight(150)
        self._detail_frame.setStyleSheet("background: #FAFAFA; border-top: 1px solid #CBD5E1;")
        self._detail_frame.setVisible(False)

        detail_layout = QVBoxLayout(self._detail_frame)
        detail_layout.setContentsMargins(12, 6, 12, 6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._detail_content = QLabel()
        self._detail_content.setWordWrap(True)
        self._detail_content.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._detail_content.setStyleSheet("font-size: 11px; color: #1E293B; line-height: 1.6;")
        scroll.setWidget(self._detail_content)
        detail_layout.addWidget(scroll)

        outer.addWidget(self._detail_frame)

    def _rebuild_detail(self) -> None:
        """HTML-Detail mit theme-passenden Farben neu aufbauen."""
        if self._dark_mode:
            viol_color = "#FCA5A5"
            warn_color = "#FCD34D"
        else:
            viol_color = "#991B1B"
            warn_color = "#92400E"

        parts = [
            f'<span style="color:{viol_color}; font-weight:600;">✕ {v}</span>'
            for v in self._violations
        ]
        parts += [
            f'<span style="color:{warn_color}; font-weight:600;">⚠ {w}</span>'
            for w in self._warnings
        ]
        self._detail_content.setText("<br>".join(parts))

    def _update_bar(self, color: str, message: str) -> None:
        self._bar.setStyleSheet(f"background-color: {color};")
        self._status_label.setText(message)
        all_msgs = self._violations + self._warnings
        self._toggle_btn.setVisible(bool(all_msgs))
        if all_msgs:
            self._rebuild_detail()
        else:
            self._detail_visible = False
            self._detail_frame.setVisible(False)

    def _toggle_detail(self) -> None:
        self._detail_visible = not self._detail_visible
        self._detail_frame.setVisible(self._detail_visible)
        self._toggle_btn.setText("Details ▴" if self._detail_visible else "Details ▾")
