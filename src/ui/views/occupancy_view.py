"""
OccupancyView – Belegungsdateneingabe für eine Planungsperiode.

Eingabe: Check-ins und Check-outs pro Tag.
Berechnet automatisch: Belegte Zimmer (rollierend), Score, Level.
"""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt, Signal, QTimer, QDate
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QSpinBox, QHeaderView,
    QDateEdit, QFrame, QMessageBox,
)

from src.database.connection import get_session
from src.database.models import DailyOccupancy
from src.domain.occupancy_calculator import calculate_occupancy_range
from src.repositories.occupancy_repository import OccupancyRepository
from src.ui.styles import OCCUPANCY_COLOR

class _AutoSelectSpinBox(QSpinBox):
    """QSpinBox, das beim Anklicken/Fokussieren automatisch den Inhalt markiert."""

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)


DAY_NAMES = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
LEVEL_DE = {"LOW": "Niedrig", "MEDIUM": "Mittel", "HIGH": "Hoch"}
LEVEL_BADGE = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}


class OccupancyView(QWidget):
    """Belegungsdateneingabe-View."""

    occupancy_saved = Signal()   # nach erfolgreichem Speichern

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._prev_occupied = 0
        self._setup_ui()
        self._load_today()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Titel + Hilfe
        title = QLabel("Hotelbelegung eingeben")
        title.setObjectName("section-title")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1E293B;")
        root.addWidget(title)

        hint = QLabel(
            "Tragen Sie Check-ins und Check-outs für jeden Tag ein. "
            "Belegte Zimmer und der Auslastungs-Score werden automatisch berechnet."
        )
        hint.setObjectName("info")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #1E293B; font-size: 12px;")
        root.addWidget(hint)

        # Startdatum
        date_row = QHBoxLayout()
        lbl_start = QLabel("Periodenstart:")
        lbl_start.setStyleSheet("color: #1E293B;")
        date_row.addWidget(lbl_start)
        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("dd.MM.yyyy")
        today = date.today()
        self._date_edit.setDate(QDate(today.year, today.month, today.day))
        date_row.addWidget(self._date_edit)

        lbl_prev = QLabel("  Vorherige Belegung:")
        lbl_prev.setStyleSheet("color: #1E293B;")
        date_row.addWidget(lbl_prev)
        self._prev_spin = _AutoSelectSpinBox()
        self._prev_spin.setRange(0, 500)
        self._prev_spin.setValue(0)
        self._prev_spin.setSuffix(" Zimmer")
        self._prev_spin.setToolTip("Belegte Zimmer am Tag vor Periodenstart (Startwert für rollierende Berechnung)")
        date_row.addWidget(self._prev_spin)
        date_row.addStretch()

        reload_btn = QPushButton("↺ Neu berechnen")
        reload_btn.clicked.connect(self._reload_table)
        date_row.addWidget(reload_btn)
        root.addLayout(date_row)

        # Tabelle
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setRowCount(14)
        self._table.setHorizontalHeaderLabels([
            "Datum", "Tag", "Check-ins", "Check-outs",
            "Belegt", "Score", "Auslastung",
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setStyleSheet(
            "QTableWidget { border: 1px solid #DDD; color: #1E293B; background: #FFFFFF; }"
            "QTableWidget::item { color: #1E293B; }"
        )
        root.addWidget(self._table, 1)

        # Speichern-Button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._save_btn = QPushButton("Belegung speichern")
        self._save_btn.setStyleSheet(
            "background: #166534; color: white; font-weight: bold;"
            "padding: 8px 20px; border-radius: 4px; border: none;"
        )
        self._save_btn.clicked.connect(self._save)
        btn_row.addWidget(self._save_btn)
        root.addLayout(btn_row)

        # SpinBox-Widgets für Check-ins / Check-outs speichern
        self._ci_spins: list[QSpinBox] = []
        self._co_spins: list[QSpinBox] = []
        self._setup_spin_widgets()

    def _setup_spin_widgets(self) -> None:
        for row in range(14):
            ci = _AutoSelectSpinBox()
            ci.setRange(0, 500)
            ci.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ci.valueChanged.connect(self._recalculate)
            self._table.setCellWidget(row, 2, ci)
            self._ci_spins.append(ci)

            co = _AutoSelectSpinBox()
            co.setRange(0, 500)
            co.setAlignment(Qt.AlignmentFlag.AlignCenter)
            co.valueChanged.connect(self._recalculate)
            self._table.setCellWidget(row, 3, co)
            self._co_spins.append(co)

    # ------------------------------------------------------------------
    # Datenladen
    # ------------------------------------------------------------------

    def _load_today(self) -> None:
        self._reload_table()

    def _reload_table(self) -> None:
        qd = self._date_edit.date()
        start = date(qd.year(), qd.month(), qd.day())
        days = [start + timedelta(days=i) for i in range(14)]

        # Vorhandene DB-Daten laden
        with get_session() as session:
            occ_repo = OccupancyRepository(session)
            rows = {r.date: r for r in occ_repo.get_range(start, days[-1])}
            prev = occ_repo.get_previous_occupied_rooms(start)

        self._prev_spin.setValue(prev)

        # Datum + Tag-Spalten befüllen; SpinBox-Werte setzen
        for row, day in enumerate(days):
            date_item = QTableWidgetItem(day.strftime("%d.%m.%Y"))
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 0, date_item)

            day_item = QTableWidgetItem(DAY_NAMES[day.weekday()])
            day_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if day.weekday() >= 5:
                day_item.setForeground(QBrush(QColor("#991B1B")))
            self._table.setItem(row, 1, day_item)

            if day in rows:
                self._ci_spins[row].setValue(rows[day].checkins)
                self._co_spins[row].setValue(rows[day].checkouts)
            else:
                self._ci_spins[row].setValue(0)
                self._co_spins[row].setValue(0)

        self._recalculate()

    def _recalculate(self) -> None:
        """Berechnet belegte Zimmer, Score, Level für alle Zeilen."""
        qd = self._date_edit.date()
        start = date(qd.year(), qd.month(), qd.day())
        days = [start + timedelta(days=i) for i in range(14)]
        prev_occ = self._prev_spin.value()

        entries = [
            (days[i], self._ci_spins[i].value(), self._co_spins[i].value())
            for i in range(14)
        ]
        results = calculate_occupancy_range(entries, initial_occupied=prev_occ)

        for row, r in enumerate(results):
            occ_item = QTableWidgetItem(str(r.occupied_rooms))
            occ_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 4, occ_item)

            score_item = QTableWidgetItem(f"{r.occupancy_score:.1f}")
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 5, score_item)

            lvl = r.occupancy_level.value
            badge = f"{LEVEL_BADGE[lvl]} {LEVEL_DE[lvl]}"
            lvl_item = QTableWidgetItem(badge)
            lvl_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            lvl_color = QColor(OCCUPANCY_COLOR[lvl])
            lvl_item.setForeground(QBrush(lvl_color))
            lvl_font = lvl_item.font()
            lvl_font.setBold(True)
            lvl_item.setFont(lvl_font)
            self._table.setItem(row, 6, lvl_item)

    # ------------------------------------------------------------------
    # Speichern
    # ------------------------------------------------------------------

    def _save(self) -> None:
        qd = self._date_edit.date()
        start = date(qd.year(), qd.month(), qd.day())
        days = [start + timedelta(days=i) for i in range(14)]
        prev_occ = self._prev_spin.value()

        entries = [
            (days[i], self._ci_spins[i].value(), self._co_spins[i].value())
            for i in range(14)
        ]
        results = calculate_occupancy_range(entries, initial_occupied=prev_occ)

        with get_session() as session:
            occ_repo = OccupancyRepository(session)
            for r in results:
                occ_repo.upsert(DailyOccupancy(
                    date=r.date,
                    checkins=r.checkins,
                    checkouts=r.checkouts,
                    occupied_rooms=r.occupied_rooms,
                    occupancy_score=r.occupancy_score,
                    occupancy_level=r.occupancy_level.value,
                ))

        QMessageBox.information(
            self, "Gespeichert",
            f"Belegungsdaten für {start.strftime('%d.%m.%Y')} – "
            f"{days[-1].strftime('%d.%m.%Y')} wurden gespeichert."
        )
        self.occupancy_saved.emit()
