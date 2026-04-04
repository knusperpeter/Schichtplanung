"""
PlanView – 2-Wochen-Schichtplan-Ansicht.

Layout:
  ┌─────────────────────────────────────────────────────┐
  │  [◀ Prev]  Periode: DD.MM – DD.MM  [Next ▶]  [Gen.] │  ← Toolbar
  ├─────────────────────────────────────────────────────┤
  │  Name  │ Mo  Di  Mi  Do  Fr  Sa  So │ Mo  Di ...    │  ← Grid
  │  Allen │  N   N   –   N   N  ...   │ ...            │
  │  ...   │ ...                        │                │
  ├─────────────────────────────────────────────────────┤
  │  Stunden-Info Leiste                                 │  ← Footer
  └─────────────────────────────────────────────────────┘
"""
from __future__ import annotations

from collections import defaultdict, Counter
from datetime import date, timedelta

from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QColor, QBrush, QFont, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QMessageBox,
)

from src.database.connection import get_session
from src.database.models import ShiftAssignment
from src.domain.enums import ShiftType, SkillLevel, RuleType, RuleScope
from src.domain.labor_law_validator import validate_employee_schedule
from src.repositories.employee_repository import EmployeeRepository
from src.repositories.occupancy_repository import OccupancyRepository
from src.repositories.plan_repository import PlanRepository
from src.ui.styles import SHIFT_BG, SHIFT_FG, SHIFT_TEXT_COLOR, SKILL_COLOR, OCCUPANCY_COLOR, STATUS_OK, STATUS_WARN, WEEKEND_HEADER_BG
from src.ui.widgets.shift_button import ShiftButton
from src.ui.dialogs.generate_dialog import GenerateDialog

DAY_NAMES = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _rule_covers(rule, day: date, shift_type: str) -> bool:
    """True wenn eine BLOCKED/VACATION/SICK-Regel den Tag und Schichttyp abdeckt."""
    scope = rule.scope
    if scope == RuleScope.SPECIFIC_DATE.value:
        if rule.specific_date != day:
            return False
    elif scope in (RuleScope.DAY_OF_WEEK.value, RuleScope.DAY_AND_SHIFT.value):
        if day.weekday() != rule.day_of_week:
            return False
    # SHIFT_TYPE: gilt für alle Tage
    if rule.shift_type and rule.shift_type != shift_type:
        return False
    return True

WEEKEND_BG      = QColor("#FFFBF0")
WEEKEND_BG_DARK = QColor("#292215")

# Auslastungs-Farben grün → gelb → rot
_OCC_COLORS = {
    "LOW":    QColor("#16A34A"),
    "MEDIUM": QColor("#D97706"),
    "HIGH":   QColor("#DC2626"),
}
_BAR_H    = 5    # Höhe des Auslastungsbalkens in Pixeln
_ROOMS_H  = 14   # Höhe der Zimmer-Zeile in Pixeln


class _DayHeaderView(QHeaderView):
    """
    Horizontaler Header mit Wochentag/Datum-Text und einem farbigen
    Auslastungsbalken am unteren Rand jeder Tagesspalte.
    """

    # Light-Mode Farben
    _LIGHT_WEEKDAY_BG = QColor("#F4F4F5")
    _LIGHT_WEEKDAY_FG = QColor("#3F3F46")
    _LIGHT_WEEKEND_BG = QColor("#FEF9C3")
    _LIGHT_WEEKEND_FG = QColor("#92400E")
    # Dark-Mode Farben
    _DARK_WEEKDAY_BG  = QColor("#18181B")
    _DARK_WEEKDAY_FG  = QColor("#F4F4F5")
    _DARK_WEEKEND_BG  = QColor("#292215")
    _DARK_WEEKEND_FG  = QColor("#FCD34D")

    def __init__(self, parent=None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._days: list[date] = []
        self._occ_map: dict = {}
        self._dark_mode = False
        self.setHighlightSections(False)
        self.setSectionsClickable(False)
        self.setFixedHeight(58)

    def set_dark_mode(self, dark: bool) -> None:
        self._dark_mode = dark
        self.viewport().update()

    def set_data(self, days: list[date], occ_map: dict) -> None:
        self._days = days
        self._occ_map = occ_map
        self.viewport().update()

    def paintSection(self, painter, rect, logical_index: int) -> None:
        if not rect.isValid() or logical_index >= len(self._days):
            super().paintSection(painter, rect, logical_index)
            return

        day = self._days[logical_index]
        is_weekend = day.weekday() >= 5
        occ = self._occ_map.get(day)

        painter.save()
        painter.setClipRect(rect)

        # Hintergrund
        if is_weekend:
            hdr_bg = self._DARK_WEEKEND_BG if self._dark_mode else self._LIGHT_WEEKEND_BG
        else:
            hdr_bg = self._DARK_WEEKDAY_BG if self._dark_mode else self._LIGHT_WEEKDAY_BG
        painter.fillRect(rect, hdr_bg)

        # Trennlinie rechts
        divider = QColor("#3F3F46") if self._dark_mode else QColor("#E4E4E7")
        painter.setPen(QPen(divider, 1))
        painter.drawLine(rect.right(), rect.top(), rect.right(), rect.bottom())

        # Wochentag + Datum (obere Hälfte)
        if is_weekend:
            date_fg = self._DARK_WEEKEND_FG if self._dark_mode else self._LIGHT_WEEKEND_FG
        else:
            date_fg = self._DARK_WEEKDAY_FG if self._dark_mode else self._LIGHT_WEEKDAY_FG
        painter.setPen(QPen(date_fg))
        font = QFont()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        date_rect = QRect(
            rect.left(), rect.top(),
            rect.width(), rect.height() - _ROOMS_H - _BAR_H,
        )
        painter.drawText(
            date_rect, Qt.AlignmentFlag.AlignCenter,
            f"{DAY_NAMES[day.weekday()]}  {day.strftime('%d.%m.')}"
        )

        # Belegte Zimmer (mittlere Zeile)
        rooms_top = rect.bottom() - _ROOMS_H - _BAR_H
        rooms_rect = QRect(rect.left(), rooms_top, rect.width(), _ROOMS_H)
        if occ:
            painter.setPen(QPen(date_fg))
            font2 = QFont()
            font2.setBold(True)
            font2.setPointSize(8)
            painter.setFont(font2)
            painter.drawText(
                rooms_rect, Qt.AlignmentFlag.AlignCenter,
                f"{occ.occupied_rooms} Zi."
            )
        else:
            no_data_fg = _HDR_WEEKEND_FG if is_weekend else QColor("#94A3B8")
            painter.setPen(QPen(no_data_fg))
            font2 = QFont()
            font2.setPointSize(7)
            painter.setFont(font2)
            painter.drawText(rooms_rect, Qt.AlignmentFlag.AlignCenter, "– Zi.")

        # Auslastungsbalken (unterste Zeile)
        if occ:
            bar_color = _OCC_COLORS.get(occ.occupancy_level, QColor("#CBD5E1"))
            bar_rect = QRect(
                rect.left() + 1,
                rect.bottom() - _BAR_H + 1,
                rect.width() - 2,
                _BAR_H - 1,
            )
            painter.fillRect(bar_rect, bar_color)

        painter.restore()


class PlanView(QWidget):
    """Haupt-Planungsansicht mit 14-Tage-Grid."""

    # Emittiert wenn sich Validierungsstatus ändert
    violations_changed = Signal(list, list)   # violations, warnings

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_period_id: int | None = None
        self._all_period_ids: list[int] = []
        self._employees: list = []
        self._days: list[date] = []
        self._dark_mode = False
        self._setup_ui()
        self._load_all_periods()

    def set_dark_mode(self, dark: bool) -> None:
        self._dark_mode = dark
        grid_color = "#3F3F46" if dark else "#E4E4E7"
        footer_border = "#3F3F46" if dark else "#E4E4E7"
        self._table.setStyleSheet(
            f"QTableWidget {{ border: none; gridline-color: {grid_color}; }}"
            "QTableWidget::item { padding: 0; border: none; }"
        )
        self._footer.setStyleSheet(
            f"padding: 6px 10px; font-size: 11px; border-top: 1px solid {footer_border};"
        )
        # Header aktualisieren
        self._day_header.set_dark_mode(dark)
        # Alle ShiftButtons aktualisieren
        for row in range(self._table.rowCount()):
            for col in range(self._table.columnCount()):
                widget = self._table.cellWidget(row, col)
                if widget is not None:
                    widget.set_dark_mode(dark)

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 6)
        root.setSpacing(8)

        # --- Toolbar ---
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        _nav_style = (
            "QPushButton { background: #18181B; color: #F4F4F5; font-weight: bold;"
            " font-size: 16px; border: none; border-radius: 6px; }"
            "QPushButton:hover { background: #27272A; }"
            "QPushButton:disabled { background: #E4E4E7; color: #A1A1AA; }"
        )
        self._prev_btn = QPushButton("<")
        self._prev_btn.setMinimumSize(48, 36)
        self._prev_btn.setStyleSheet(_nav_style)
        self._prev_btn.clicked.connect(self._go_prev)
        toolbar.addWidget(self._prev_btn)

        self._period_label = QLabel("Keine Periode geladen")
        self._period_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        self._period_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(self._period_label, 1)

        self._next_btn = QPushButton(">")
        self._next_btn.setMinimumSize(48, 36)
        self._next_btn.setStyleSheet(_nav_style)
        self._next_btn.clicked.connect(self._go_next)
        toolbar.addWidget(self._next_btn)

        toolbar.addSpacing(20)

        self._gen_btn = QPushButton("  Plan generieren  ")
        self._gen_btn.setObjectName("primary")
        self._gen_btn.setStyleSheet(
            "background: #18181B; color: #FAFAFA; font-weight: 600;"
            "padding: 6px 14px; border-radius: 6px; border: none; font-size: 12px;"
        )
        self._gen_btn.clicked.connect(self._open_generate_dialog)
        toolbar.addWidget(self._gen_btn)

        root.addLayout(toolbar)

        # --- Legende ---
        legend = QHBoxLayout()
        legend.setSpacing(12)
        for code, label in [("F", "Früh"), ("Z", "Zwischen"), ("S", "Spät"), ("N", "Nacht")]:
            dot = QLabel(f"● {label}")
            dot.setStyleSheet(
                f"color: {SHIFT_TEXT_COLOR[code]}; font-size: 11px; font-weight: bold;"
            )
            legend.addWidget(dot)
        legend.addStretch()
        manual_hint = QLabel("* = manuell geändert")
        manual_hint.setStyleSheet("font-size: 10px; font-style: italic;")
        legend.addWidget(manual_hint)
        root.addLayout(legend)

        # --- Grid ---
        self._table = QTableWidget()
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Custom Header mit Auslastungsbalken
        self._day_header = _DayHeaderView(self._table)
        self._day_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._day_header.setMinimumSectionSize(38)
        self._table.setHorizontalHeader(self._day_header)

        self._table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setMinimumSectionSize(28)
        self._table.setShowGrid(True)
        self._table.setAlternatingRowColors(False)
        self._table.setStyleSheet(
            "QTableWidget { border: none; gridline-color: #E4E4E7; }"
            "QTableWidget::item { padding: 0; border: none; }"
        )
        root.addWidget(self._table, 1)

        # --- Footer: Stundenübersicht ---
        self._footer = QLabel("–")
        self._footer.setStyleSheet(
            "padding: 6px 10px; font-size: 11px; border-top: 1px solid #E4E4E7;"
        )
        self._footer.setWordWrap(True)
        root.addWidget(self._footer)

    # ------------------------------------------------------------------
    # Datenladen
    # ------------------------------------------------------------------

    def _load_all_periods(self) -> None:
        with get_session() as session:
            periods = PlanRepository(session).get_all_periods()
        self._all_period_ids = [p.id for p in periods]
        if self._all_period_ids:
            self.load_period(self._all_period_ids[0])
        else:
            self._period_label.setText("Keine Periode – Plan generieren")
            self._prev_btn.setEnabled(False)
            self._next_btn.setEnabled(False)

    def load_period(self, period_id: int) -> None:
        self._current_period_id = period_id

        with get_session() as session:
            plan_repo = PlanRepository(session)
            emp_repo  = EmployeeRepository(session)
            occ_repo  = OccupancyRepository(session)

            period = plan_repo.get_period_by_id(period_id)
            if not period:
                return

            employees   = emp_repo.get_all()
            assignments = plan_repo.get_assignments_for_period(period_id)
            start, end  = period.start_date, period.end_date
            occ_rows    = occ_repo.get_range(start, end)

        self._employees = employees
        self._days = [start + timedelta(days=i) for i in range((end - start).days + 1)]

        self._period_label.setText(
            f"Periode:  {start.strftime('%d.%m.%Y')}  –  {end.strftime('%d.%m.%Y')}"
        )

        occ_map = {r.date: r for r in occ_rows}
        self._populate_grid(employees, self._days, assignments, occ_map)
        self._update_nav_buttons()
        self._run_validation(assignments, employees)
        self._update_footer(assignments, employees)

    def _populate_grid(self, employees, days, assignments, occ_map) -> None:
        # Assignment-Lookup: (emp_id, date) → ShiftAssignment
        asgn_map: dict[tuple[int, date], ShiftAssignment] = {
            (a.employee_id, a.date): a for a in assignments
        }

        n_emps = len(employees)
        n_days = len(days)

        self._table.blockSignals(True)
        self._table.setRowCount(n_emps)
        self._table.setColumnCount(n_days)

        # Custom Header mit Tagen + Auslastungsbalken befüllen
        self._day_header.set_dark_mode(self._dark_mode)
        self._day_header.set_data(days, occ_map)

        # Vertikale Header + Zellen
        for row, emp in enumerate(employees):
            # Zeilen-Header: Name + Skill-Farbe
            h_item = QTableWidgetItem(f" {emp.name}")
            h_item.setFont(QFont("", 11, QFont.Weight.Bold))
            h_item.setForeground(QBrush(QColor(SKILL_COLOR.get(emp.skill_level, "#1E293B"))))
            self._table.setVerticalHeaderItem(row, h_item)

            # Schicht-Buttons
            for col, day in enumerate(days):
                asgn = asgn_map.get((emp.id, day))
                shift_type = asgn.shift_type if asgn else ""
                is_manual  = asgn.is_manual_override if asgn else False

                btn = ShiftButton(shift_type, emp.id, day, is_manual=is_manual)
                btn.set_dark_mode(self._dark_mode)
                btn.shift_changed.connect(self._on_shift_changed)
                self._table.setCellWidget(row, col, btn)

        # Wochenend-Spalten optisch hervorheben
        weekend_color = WEEKEND_BG_DARK if self._dark_mode else WEEKEND_BG
        for d_idx, day in enumerate(days):
            if day.weekday() >= 5:
                for row in range(n_emps):
                    item = self._table.item(row, d_idx)
                    if item is None:
                        item = QTableWidgetItem()
                        self._table.setItem(row, d_idx, item)
                    item.setBackground(QBrush(weekend_color))

        self._table.verticalHeader().setMinimumWidth(140)
        self._table.blockSignals(False)

    # ------------------------------------------------------------------
    # Schicht-Änderung
    # ------------------------------------------------------------------

    def _on_shift_changed(self, emp_id: int, day: date, shift_type: str) -> None:
        if self._current_period_id is None:
            return

        with get_session() as session:
            plan_repo = PlanRepository(session)

            # Bestehende Zuweisung für diesen MA + Tag löschen
            existing = plan_repo.get_assignments_on_date(day, self._current_period_id)
            for a in existing:
                if a.employee_id == emp_id:
                    plan_repo.delete_assignment(a)

            # Neue Zuweisung anlegen (wenn nicht "frei")
            if shift_type:
                plan_repo.add_assignment(ShiftAssignment(
                    period_id=self._current_period_id,
                    date=day,
                    shift_type=shift_type,
                    employee_id=emp_id,
                    is_manual_override=True,
                ))

            # Frischen Stand laden für Validierung + Footer
            all_assignments = plan_repo.get_assignments_for_period(self._current_period_id)

        self._run_validation(all_assignments, self._employees)
        self._update_footer(all_assignments, self._employees)

    # ------------------------------------------------------------------
    # Validierung
    # ------------------------------------------------------------------

    def _run_validation(self, assignments, employees) -> None:
        emp_map = {e.id: e for e in employees}
        emp_shifts: dict[int, list] = defaultdict(list)
        for a in assignments:
            emp_shifts[a.employee_id].append((a.date, ShiftType(a.shift_type)))

        violation_msgs: list[str] = []

        # V1 – Ruhezeit (ArbZG §5)
        for emp_id, shifts in emp_shifts.items():
            emp = emp_map.get(emp_id)
            name = emp.name if emp else str(emp_id)
            for v in validate_employee_schedule(name, shifts):
                violation_msgs.append(v.message)

        # V2 – Verfügbarkeitsregeln (Urlaub, Krank, Gesperrt)
        _type_label = {"BLOCKED": "Gesperrt", "VACATION": "Urlaub", "SICK": "Krank"}
        for a in assignments:
            emp = emp_map.get(a.employee_id)
            if not emp:
                continue
            for rule in emp.availability_rules:
                rt = rule.rule_type
                if rt not in _type_label:
                    continue
                if not _rule_covers(rule, a.date, a.shift_type):
                    continue
                violation_msgs.append(
                    f"{emp.name}: Schicht {a.shift_type} am {a.date.strftime('%d.%m.')} "
                    f"– Regel \"{_type_label[rt]}\" verletzt"
                )

        # V3 – Nachtschicht nur für EXPERT
        for a in assignments:
            emp = emp_map.get(a.employee_id)
            if emp and a.shift_type == ShiftType.NIGHT.value:
                if emp.skill_level != SkillLevel.EXPERT.value:
                    violation_msgs.append(
                        f"{emp.name}: Nachtschicht am {a.date.strftime('%d.%m.')} "
                        f"– nur Experten erlaubt"
                    )

        # V4 – BEGINNER auf Spät ohne zweite Person auf Spät
        late_per_day: dict = defaultdict(list)
        for a in assignments:
            if a.shift_type == ShiftType.LATE.value:
                late_per_day[a.date].append(a.employee_id)
        for day, ids in late_per_day.items():
            for eid in ids:
                emp = emp_map.get(eid)
                if emp and emp.skill_level == SkillLevel.BEGINNER.value:
                    if len(ids) < 2:
                        violation_msgs.append(
                            f"{emp.name}: Spätschicht am {day.strftime('%d.%m.')} "
                            f"ohne zweite Person auf Spät"
                        )

        # Warnungen: Stundenabweichung + Wochenlimit
        warnings: list[str] = []
        shifts_per_emp = Counter(a.employee_id for a in assignments)
        for e in employees:
            actual = shifts_per_emp.get(e.id, 0) * 8.5
            target = e.target_hours_per_month / 2
            if target > 0 and abs(actual - target) > 12:
                delta = actual - target
                sign = "+" if delta > 0 else ""
                warnings.append(
                    f"{e.name}: {sign}{delta:.0f}h Abweichung von Periodensziel ({target:.0f}h)"
                )

        # W2 – Wochenlimit: MAX_20 max 2 Schichten, alle max 5
        from src.domain.enums import ContractType
        week_shifts: dict[tuple[int, int], int] = defaultdict(int)
        for a in assignments:
            week_key = (a.employee_id, a.date.isocalendar().week)
            week_shifts[week_key] += 1
        for e in employees:
            for week in range(2):
                d_start = self._days[week * 7] if self._days else None
                if d_start is None:
                    break
                kw = d_start.isocalendar().week
                n = week_shifts.get((e.id, kw), 0)
                limit = 2 if e.contract_type == ContractType.MAX_20.value else 5
                if n > limit:
                    warnings.append(
                        f"{e.name}: KW {kw} – {n} Schichten (Limit: {limit})"
                    )

        self.violations_changed.emit(violation_msgs, warnings)

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------

    def _update_footer(self, assignments, employees) -> None:
        shifts_per_emp = Counter(a.employee_id for a in assignments)
        parts = []
        for e in employees:
            n = shifts_per_emp.get(e.id, 0)
            weekly_h = n * 8.5 / 2
            parts.append(f"{e.name}: {weekly_h:.1f}h/Woche")
        self._footer.setText("  ·  ".join(parts))

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _go_prev(self) -> None:
        if self._current_period_id in self._all_period_ids:
            idx = self._all_period_ids.index(self._current_period_id)
            if idx + 1 < len(self._all_period_ids):
                self.load_period(self._all_period_ids[idx + 1])

    def _go_next(self) -> None:
        if self._current_period_id in self._all_period_ids:
            idx = self._all_period_ids.index(self._current_period_id)
            if idx > 0:
                self.load_period(self._all_period_ids[idx - 1])

    def _update_nav_buttons(self) -> None:
        if not self._all_period_ids or self._current_period_id is None:
            self._prev_btn.setEnabled(False)
            self._next_btn.setEnabled(False)
            return
        idx = self._all_period_ids.index(self._current_period_id)
        self._prev_btn.setEnabled(idx + 1 < len(self._all_period_ids))
        self._next_btn.setEnabled(idx > 0)

    # ------------------------------------------------------------------
    # Plan generieren
    # ------------------------------------------------------------------

    def _open_generate_dialog(self) -> None:
        dlg = GenerateDialog(self)
        dlg.plan_generated.connect(self._on_plan_generated)
        dlg.exec()

    def _on_plan_generated(self, period_id: int) -> None:
        self._load_all_periods()
        self.load_period(period_id)
