"""
GenerateDialog – Planungsdialog mit Perioden-Auswahl und Fortschrittsanzeige.

Ablauf:
  1. Nutzer wählt Periodenstartdatum (Montag vorgeschlagen)
  2. Dialog zeigt Belegungsstatus der Periode an
  3. Klick auf "Generieren" startet CP-SAT-Solver im Hintergrund
  4. Fortschrittsanzeige während Solver läuft
  5. Ergebnis wird in DB gespeichert → Dialog schließt
"""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDateEdit, QProgressBar, QFrame, QMessageBox,
)
from PySide6.QtCore import QDate

from src.database.connection import get_session
from src.database.models import PlanningPeriod, ShiftAssignment
from src.domain.hour_balance_tracker import HourBalanceTracker
from src.domain.occupancy_calculator import calculate_occupancy_range, OccupancyResult
from src.domain.scheduler import CPSATScheduler, SchedulerInput
from src.repositories.employee_repository import EmployeeRepository
from src.repositories.occupancy_repository import OccupancyRepository
from src.repositories.plan_repository import PlanRepository
from src.ui.styles import OCCUPANCY_COLOR, STATUS_OK, STATUS_WARN, STATUS_ERROR


# ---------------------------------------------------------------------------
# Background Worker
# ---------------------------------------------------------------------------

class SchedulerWorker(QThread):
    result_ready = Signal(object)    # SchedulerResult
    error_occurred = Signal(str)

    def __init__(self, scheduler_input: SchedulerInput) -> None:
        super().__init__()
        self._input = scheduler_input

    def run(self) -> None:
        try:
            scheduler = CPSATScheduler(self._input)
            result = scheduler.schedule()
            self.result_ready.emit(result)
        except Exception as exc:
            self.error_occurred.emit(str(exc))


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class GenerateDialog(QDialog):
    """
    Dialog zum Generieren eines neuen Schichtplans.

    Signals:
        plan_generated(period_id): Wird nach erfolgreicher Generierung emittiert.
    """

    plan_generated = Signal(int)   # period_id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Schichtplan generieren")
        self.setMinimumWidth(480)
        self.setModal(True)
        self._worker: SchedulerWorker | None = None
        self._period_id: int | None = None
        self._setup_ui()
        self._on_date_changed()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Titel
        title = QLabel("Neuen Schichtplan erstellen")
        title.setObjectName("section-title")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #E4E4E7;")
        layout.addWidget(sep)

        # Datumswahl
        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Perioden-Start (Montag):"))
        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("dd.MM.yyyy")
        start = self._next_monday()
        self._date_edit.setDate(QDate(start.year, start.month, start.day))
        self._date_edit.dateChanged.connect(self._on_date_changed)
        date_row.addWidget(self._date_edit)
        date_row.addStretch()
        layout.addLayout(date_row)

        # Perioden-Info
        self._period_info = QLabel()
        self._period_info.setStyleSheet("font-size: 12px;")
        layout.addWidget(self._period_info)

        # Belegungsstatus
        self._occ_frame = QFrame()
        self._occ_frame.setObjectName("card")
        occ_layout = QVBoxLayout(self._occ_frame)
        occ_layout.setContentsMargins(10, 8, 10, 8)
        occ_layout.setSpacing(3)
        self._occ_title = QLabel("Belegungsdaten")
        self._occ_title.setObjectName("section-title")
        occ_layout.addWidget(self._occ_title)
        self._occ_status = QLabel()
        self._occ_status.setStyleSheet("font-size: 11px;")
        self._occ_status.setWordWrap(True)
        occ_layout.addWidget(self._occ_status)
        layout.addWidget(self._occ_frame)

        # Fortschrittsbereich (zunächst verborgen)
        self._progress_frame = QFrame()
        prog_layout = QVBoxLayout(self._progress_frame)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)   # indeterminate
        prog_layout.addWidget(self._progress_bar)
        self._progress_label = QLabel("Solver läuft…")
        self._progress_label.setStyleSheet("font-size: 11px;")
        prog_layout.addWidget(self._progress_label)
        self._progress_frame.setVisible(False)
        layout.addWidget(self._progress_frame)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton("Abbrechen")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)
        self._generate_btn = QPushButton("Generieren")
        self._generate_btn.setObjectName("primary")
        self._generate_btn.clicked.connect(self._start_generation)
        btn_row.addWidget(self._generate_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Logik
    # ------------------------------------------------------------------

    @staticmethod
    def _next_monday() -> date:
        today = date.today()
        days_ahead = (7 - today.weekday()) % 7 or 7
        return today + timedelta(days=days_ahead)

    def _get_period_dates(self) -> tuple[date, date]:
        qd = self._date_edit.date()
        start = date(qd.year(), qd.month(), qd.day())
        end = start + timedelta(days=13)
        return start, end

    def _on_date_changed(self) -> None:
        start, end = self._get_period_dates()
        self._period_info.setText(
            f"Periode: <b>{start.strftime('%d.%m.%Y')}</b> – <b>{end.strftime('%d.%m.%Y')}</b> (14 Tage)"
        )
        self._load_occupancy_status(start, end)

    def _load_occupancy_status(self, start: date, end: date) -> None:
        with get_session() as session:
            occ_repo = OccupancyRepository(session)
            rows = occ_repo.get_range(start, end)

        days_with_data = len(rows)
        total_days = 14

        if days_with_data == 0:
            color = STATUS_ERROR
            msg = (
                f"⚠ Keine Belegungsdaten für diese Periode vorhanden. "
                f"Bitte zuerst im Tab 'Belegung' eintragen.\n"
                f"Ohne Daten wird LOW-Auslastung angenommen."
            )
        elif days_with_data < total_days:
            color = STATUS_WARN
            missing = total_days - days_with_data
            msg = (
                f"⚠ {days_with_data}/{total_days} Tage mit Daten. "
                f"{missing} Tage fehlen (LOW angenommen)."
            )
        else:
            high = sum(1 for r in rows if r.occupancy_level == "HIGH")
            med  = sum(1 for r in rows if r.occupancy_level == "MEDIUM")
            color = STATUS_OK
            msg = (
                f"✓ Alle {total_days} Tage mit Belegungsdaten. "
                f"HIGH: {high} Tage · MEDIUM: {med} Tage"
            )

        self._occ_status.setText(msg)
        self._occ_status.setStyleSheet(f"font-size: 11px; color: {color};")

    def _start_generation(self) -> None:
        start, end = self._get_period_dates()

        # Inputs aus DB laden
        with get_session() as session:
            employees = EmployeeRepository(session).get_all()
            occ_repo = OccupancyRepository(session)
            occ_rows = occ_repo.get_range(start, end)

            # Belegung berechnen (rollierend)
            raw = [(r.date, r.checkins, r.checkouts) for r in occ_rows]
            # Fehlende Tage mit 0 auffüllen
            existing_dates = {r.date for r in occ_rows}
            day = start
            while day <= end:
                if day not in existing_dates:
                    raw.append((day, 0, 0))
                day += timedelta(days=1)
            raw.sort(key=lambda x: x[0])

            prev_occ = occ_repo.get_previous_occupied_rooms(start)
            occ_results = calculate_occupancy_range(raw, initial_occupied=prev_occ)
            occupancy_map = {r.date: r for r in occ_results}

            # Periode anlegen / ersetzen
            plan_repo = PlanRepository(session)
            existing = plan_repo.get_period_for_date(start)
            if existing:
                plan_repo.delete_period(existing)
            period = plan_repo.create_period(PlanningPeriod(start_date=start, end_date=end))
            self._period_id = period.id

            # Zielschichten berechnen
            tracker = HourBalanceTracker()
            target_shifts = {
                e.id: tracker.period_target_shifts(e, start, end)
                for e in employees
            }

            scheduler_input = SchedulerInput(
                period=period,
                employees=employees,
                occupancy=occupancy_map,
                target_shifts_per_employee=target_shifts,
            )

        # UI in Löse-Modus schalten
        self._generate_btn.setEnabled(False)
        self._date_edit.setEnabled(False)
        self._progress_frame.setVisible(True)
        self._progress_label.setText("CP-SAT Solver läuft (max. 30s)…")

        # Worker starten
        self._worker = SchedulerWorker(scheduler_input)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _on_result(self, result) -> None:
        self._progress_frame.setVisible(False)

        if result.status == "INFEASIBLE":
            QMessageBox.critical(
                self, "Kein Plan möglich",
                "Der Solver konnte keinen gültigen Plan finden.\n\n"
                "Mögliche Ursachen:\n"
                "• Zu viele Sperrtage für Frühschicht oder Nachtschicht\n"
                "• Nicht genug Mitarbeiter für Pflicht-Schichten\n\n"
                "Bitte Verfügbarkeitsregeln prüfen.",
            )
            self._generate_btn.setEnabled(True)
            self._date_edit.setEnabled(True)
            return

        # Assignments in DB speichern
        with get_session() as session:
            plan_repo = PlanRepository(session)
            plan_repo.delete_all_assignments_for_period(self._period_id)
            for a in result.assignments:
                plan_repo.add_assignment(a)

            # Stundenkonten aktualisieren
            employees = EmployeeRepository(session).get_all()
            tracker = HourBalanceTracker()
            tracker.update_balances(session, result.assignments, employees)

        status_text = {
            "OPTIMAL": "Optimal",
            "FEASIBLE": "Gültige Lösung (nicht bewiesen optimal)",
        }.get(result.status, result.status)

        self._progress_label.setText(
            f"✓ Fertig – {status_text} · {len(result.assignments)} Schichten "
            f"· {result.solve_time_seconds:.1f}s"
        )
        self._progress_label.setStyleSheet(f"color: {STATUS_OK}; font-size: 11px;")
        self._progress_frame.setVisible(True)

        self.plan_generated.emit(self._period_id)

        if result.warnings:
            QMessageBox.warning(
                self, "Hinweise", "\n".join(result.warnings)
            )

        self.accept()

    def _on_error(self, error_msg: str) -> None:
        self._progress_frame.setVisible(False)
        self._generate_btn.setEnabled(True)
        self._date_edit.setEnabled(True)
        QMessageBox.critical(self, "Fehler beim Generieren", error_msg)

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(3000)
        super().closeEvent(event)
