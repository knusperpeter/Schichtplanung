"""
CP-SAT Scheduler – generiert einen optimierten 2-Wochen-Schichtplan.

Modellstruktur:
  Entscheidungsvariablen:
      works[emp_id, day_idx, shift_value] ∈ {0, 1}

  Hard Constraints (H1–H13):
      H1  Verfügbarkeitsregeln (blocked shifts/days/dates)
      H2  11h Ruhezeit (ArbZG §5) – verbotene Schichtfolgen
      H3  Max 1 Schicht pro Tag pro Mitarbeiter
      H4  Max 5 Schichten/Woche (≤ 48h/Woche, ArbZG §3)
      H5  max_late_shifts_per_week (Simon: max 2 Spät/Woche)
      H6  Nachtschicht nur für EXPERT
      H7  BEGINNER auf Spät → mind. 1 weitere Person auf Spät (gleicher Zeitraum)
      H8  Frühschicht genau 1 Person, Nachtschicht genau 1 Person
      H_S Spätschicht mind. 1 Person
      H_Z Zwischenschicht wenn Auslastung ≥ 60 Zimmer (Pflicht)
      H11 MAX_20-Vertrag: max 2 Schichten/Woche
      H12 FULLTIME_40: max 6 aufeinanderfolgende Arbeitstage (ArbZG §11)
      H13 MAX_20: max 3 aufeinanderfolgende Arbeitstage

  Soft Constraints / Objective Penalties (S1–S6):
      S1  Jasmin → Zwischenschicht bevorzugen      (Gewicht 10)
      S2  Night-Präferenz (Allen, Simon)            (Gewicht 9)
      S3  Stundenkonto-Abweichung minimieren        (Gewicht 15)
      S4  AVOID-Regeln (Benze: kein Sonntag)        (Gewicht 7)
      S5  Schichtblockwechsel ohne 2-Tage-Pause     (Gewicht 6)
      S6  FULLTIME_40: 6 aufeinanderfolgende Tage penalisieren (Norm: 5) (Gewicht 5)
"""
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

try:
    from ortools.sat.python import cp_model as _cp_model_module
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False

from src.database.models import Employee, ShiftAssignment, PlanningPeriod
from src.domain.enums import (
    ShiftType, SkillLevel, ContractType, RuleType, RuleScope, ShiftBlock,
)
from src.domain.occupancy_calculator import OccupancyResult
from src.domain.labor_law_validator import FORBIDDEN_NEXT_DAY

ALL_SHIFTS = [ShiftType.EARLY, ShiftType.MIDDLE, ShiftType.LATE, ShiftType.NIGHT]
MAX_SHIFTS_PER_WEEK = 5          # 5 × 8,5h = 42,5h ≤ 48h (ArbZG §3)
MAX_SHIFTS_PER_WEEK_MAX20 = 2    # 2 × 8,5h = 17h ≤ 20h


# ---------------------------------------------------------------------------
# EmployeeConstraintCache
# ---------------------------------------------------------------------------

class EmployeeConstraintCache:
    """
    Vorberechnete Constraint-Informationen für einen Mitarbeiter.
    Wird einmal pro Solver-Lauf erstellt, um wiederholte DB-Abfragen zu vermeiden.
    """

    def __init__(self, employee: Employee, days: list[date]) -> None:
        self.employee = employee
        self._blocked: set[tuple[int, str]] = set()       # (day_idx, shift_value)
        self._preferred_shifts: set[str] = set()          # shift_value strings
        self._avoided_days_of_week: set[int] = set()      # 0=Mo … 6=So
        self._build(days)

    def _build(self, days: list[date]) -> None:
        for rule in self.employee.availability_rules:
            rt = rule.rule_type

            if rt == RuleType.PREFERRED.value:
                if rule.scope == RuleScope.SHIFT_TYPE.value and rule.shift_type:
                    self._preferred_shifts.add(rule.shift_type)
                continue

            if rt == RuleType.AVOID.value:
                if rule.scope == RuleScope.DAY_OF_WEEK.value and rule.day_of_week is not None:
                    self._avoided_days_of_week.add(rule.day_of_week)
                continue

            # BLOCKED / VACATION / SICK
            if rt not in (RuleType.BLOCKED.value, RuleType.VACATION.value, RuleType.SICK.value):
                continue

            for d_idx, day in enumerate(days):
                if not self._day_matches(rule, day):
                    continue
                if rule.shift_type:
                    self._blocked.add((d_idx, rule.shift_type))
                else:
                    # Kein konkreter Schichttyp → alle Schichten sperren
                    for s in ALL_SHIFTS:
                        self._blocked.add((d_idx, s.value))

    @staticmethod
    def _day_matches(rule, day: date) -> bool:
        match rule.scope:
            case RuleScope.SHIFT_TYPE.value:
                return True          # gilt für alle Tage
            case RuleScope.DAY_OF_WEEK.value:
                return day.weekday() == rule.day_of_week
            case RuleScope.SPECIFIC_DATE.value:
                return rule.specific_date == day
            case RuleScope.DAY_AND_SHIFT.value:
                return day.weekday() == rule.day_of_week
        return False

    def is_blocked(self, day_idx: int, shift: ShiftType) -> bool:
        return (day_idx, shift.value) in self._blocked

    def prefers(self, shift: ShiftType) -> bool:
        return shift.value in self._preferred_shifts

    def avoids_day(self, day: date) -> bool:
        return day.weekday() in self._avoided_days_of_week


# ---------------------------------------------------------------------------
# Data-Transfer-Objekte
# ---------------------------------------------------------------------------

@dataclass
class SchedulerInput:
    period: PlanningPeriod
    employees: list[Employee]                      # inkl. geladener availability_rules
    occupancy: dict[date, OccupancyResult]         # Belegung je Datum
    target_shifts_per_employee: dict[int, int]     # emp_id → Zielschichten für Periode


@dataclass
class SchedulerResult:
    assignments: list[ShiftAssignment]
    status: str            # "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "UNKNOWN"
    solve_time_seconds: float
    objective_value: Optional[int]
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# CPSATScheduler
# ---------------------------------------------------------------------------

class CPSATScheduler:
    """Generiert einen Schichtplan mit dem OR-Tools CP-SAT Solver."""

    def __init__(self, inp: SchedulerInput) -> None:
        if not ORTOOLS_AVAILABLE:
            raise RuntimeError(
                "OR-Tools nicht installiert.\n"
                "Bitte ausführen: python3 -m pip install ortools"
            )
        self.inp = inp
        self.days: list[date] = self._build_days()
        self.num_days = len(self.days)
        self.caches: dict[int, EmployeeConstraintCache] = {
            e.id: EmployeeConstraintCache(e, self.days)
            for e in inp.employees
        }

    def _build_days(self) -> list[date]:
        days = []
        cur = self.inp.period.start_date
        while cur <= self.inp.period.end_date:
            days.append(cur)
            cur += timedelta(days=1)
        return days

    # ------------------------------------------------------------------
    # Hauptmethode
    # ------------------------------------------------------------------

    def schedule(self) -> SchedulerResult:
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        employees = self.inp.employees
        num_days = self.num_days

        # --- Entscheidungsvariablen ---
        works: dict[tuple[int, int, str], any] = {
            (e.id, d, s.value): model.new_bool_var(f"w_{e.id}_{d}_{s.value}")
            for e in employees
            for d in range(num_days)
            for s in ALL_SHIFTS
        }

        # ==============================================================
        # HARD CONSTRAINTS
        # ==============================================================

        # H1 – Verfügbarkeitsregeln
        for e in employees:
            cache = self.caches[e.id]
            for d in range(num_days):
                for s in ALL_SHIFTS:
                    if cache.is_blocked(d, s):
                        model.add(works[e.id, d, s.value] == 0)

        # H2 – 11h Ruhezeit: verbotene Schichtfolgen an aufeinanderfolgenden Tagen
        for e in employees:
            for d in range(num_days - 1):
                for s1, s2 in FORBIDDEN_NEXT_DAY:
                    model.add(works[e.id, d, s1.value] + works[e.id, d + 1, s2.value] <= 1)

        # H3 – Max 1 Schicht pro Tag
        for e in employees:
            for d in range(num_days):
                model.add(sum(works[e.id, d, s.value] for s in ALL_SHIFTS) <= 1)

        # Hilfsvariable: works_day[e.id, d] = 1 wenn e an Tag d irgendeinen Dienst hat
        works_day: dict[tuple[int, int], any] = {}
        for e in employees:
            for d in range(num_days):
                wd = model.new_bool_var(f"wd_{e.id}_{d}")
                model.add(wd == sum(works[e.id, d, s.value] for s in ALL_SHIFTS))
                works_day[e.id, d] = wd

        # H4 – Max 48h/Woche = max 5 Schichten/Woche
        for e in employees:
            for week in range(2):
                d_start, d_end = week * 7, min((week + 1) * 7, num_days)
                model.add(
                    sum(works[e.id, d, s.value]
                        for d in range(d_start, d_end)
                        for s in ALL_SHIFTS) <= MAX_SHIFTS_PER_WEEK
                )

        # H5 – max_late_shifts_per_week (individuell)
        for e in employees:
            if e.max_late_shifts_per_week is not None:
                for week in range(2):
                    d_start, d_end = week * 7, min((week + 1) * 7, num_days)
                    model.add(
                        sum(works[e.id, d, ShiftType.LATE.value]
                            for d in range(d_start, d_end)) <= e.max_late_shifts_per_week
                    )

        # H6 – Nachtschicht nur für EXPERT
        for e in employees:
            if e.skill_level != SkillLevel.EXPERT.value:
                for d in range(num_days):
                    model.add(works[e.id, d, ShiftType.NIGHT.value] == 0)

        # H8 – Frühschicht genau 1, Nachtschicht genau 1
        for d in range(num_days):
            model.add(sum(works[e.id, d, ShiftType.EARLY.value] for e in employees) == 1)
            model.add(sum(works[e.id, d, ShiftType.NIGHT.value] for e in employees) == 1)

        # H_S – Spätschicht mind. 1 Person
        for d in range(num_days):
            model.add(sum(works[e.id, d, ShiftType.LATE.value] for e in employees) >= 1)

        # H_Z – Zwischenschicht Pflicht bei hoher Auslastung
        for d, day in enumerate(self.days):
            occ = self.inp.occupancy.get(day)
            if occ and occ.requires_between_shift:
                model.add(
                    sum(works[e.id, d, ShiftType.MIDDLE.value] for e in employees) >= 1
                )

        # H7 – BEGINNER auf Spät benötigt immer eine zweite Person auf Spät
        beginners = [e for e in employees if e.skill_level == SkillLevel.BEGINNER.value]
        for beg in beginners:
            for d in range(num_days):
                support = sum(
                    works[e.id, d, ShiftType.LATE.value]
                    for e in employees if e.id != beg.id
                )
                model.add(works[beg.id, d, ShiftType.LATE.value] <= support)

        # H11 – MAX_20-Vertrag: max 2 Schichten/Woche
        for e in employees:
            if e.contract_type == ContractType.MAX_20.value:
                for week in range(2):
                    d_start, d_end = week * 7, min((week + 1) * 7, num_days)
                    model.add(
                        sum(works[e.id, d, s.value]
                            for d in range(d_start, d_end)
                            for s in ALL_SHIFTS) <= MAX_SHIFTS_PER_WEEK_MAX20
                    )

        # H12 – FULLTIME_40: max 6 aufeinanderfolgende Arbeitstage
        # In jedem 7-Tage-Fenster darf der Mitarbeiter max. 6 Tage arbeiten.
        for e in employees:
            if e.contract_type == ContractType.FULLTIME_40.value:
                for d in range(num_days - 6):
                    model.add(
                        sum(works_day[e.id, d + i] for i in range(7)) <= 6
                    )

        # H13 – MAX_20: max 3 aufeinanderfolgende Arbeitstage
        # In jedem 4-Tage-Fenster darf der Mitarbeiter max. 3 Tage arbeiten.
        for e in employees:
            if e.contract_type == ContractType.MAX_20.value:
                for d in range(num_days - 3):
                    model.add(
                        sum(works_day[e.id, d + i] for i in range(4)) <= 3
                    )

        # ==============================================================
        # SOFT CONSTRAINTS / OBJECTIVE
        # ==============================================================
        objective_terms = []

        # S1 – prefers_between_shift (Jasmin) → penalize non-Zwischen
        for e in employees:
            if e.prefers_between_shift:
                for d in range(num_days):
                    for s in [ShiftType.EARLY, ShiftType.LATE, ShiftType.NIGHT]:
                        objective_terms.append(10 * works[e.id, d, s.value])

        # S2 – Nacht-Präferenz → penalize non-Nacht
        for e in employees:
            cache = self.caches[e.id]
            if cache.prefers(ShiftType.NIGHT):
                for d in range(num_days):
                    for s in [ShiftType.EARLY, ShiftType.MIDDLE, ShiftType.LATE]:
                        objective_terms.append(9 * works[e.id, d, s.value])

        # S3 – Stundenkonto: Abweichung von Zielschichten minimieren
        for e in employees:
            target = self.inp.target_shifts_per_employee.get(e.id, 0)
            total_shifts = model.new_int_var(0, num_days, f"total_{e.id}")
            model.add(
                total_shifts == sum(
                    works[e.id, d, s.value]
                    for d in range(num_days)
                    for s in ALL_SHIFTS
                )
            )
            deviation = model.new_int_var(0, num_days, f"dev_{e.id}")
            model.add_abs_equality(deviation, total_shifts - target)
            objective_terms.append(15 * deviation)

        # S4 – AVOID-Regeln (z.B. Benze meidet Sonntag)
        for e in employees:
            cache = self.caches[e.id]
            for d, day in enumerate(self.days):
                if cache.avoids_day(day):
                    for s in ALL_SHIFTS:
                        objective_terms.append(7 * works[e.id, d, s.value])

        # S5 – Schichtblockwechsel an aufeinanderfolgenden Tagen penalisieren
        # (Idealfall: 2 freie Tage zwischen Blockwechsel)
        _block = {
            ShiftType.EARLY:  ShiftBlock.MORNING,
            ShiftType.MIDDLE: ShiftBlock.MORNING,
            ShiftType.LATE:   ShiftBlock.EVENING,
            ShiftType.NIGHT:  ShiftBlock.NIGHT,
        }
        for e in employees:
            for d in range(num_days - 1):
                for s1 in ALL_SHIFTS:
                    for s2 in ALL_SHIFTS:
                        if _block[s1] == _block[s2]:
                            continue          # gleicher Block – kein Wechsel
                        if (s1, s2) in FORBIDDEN_NEXT_DAY:
                            continue          # bereits als Hard Constraint
                        # Hilfsvariable: 1 ↔ beide works gesetzt
                        bc = model.new_bool_var(f"bc_{e.id}_{d}_{s1.value}_{s2.value}")
                        # bc ≤ works[d][s1]  und  bc ≤ works[d+1][s2]
                        model.add(bc <= works[e.id, d, s1.value])
                        model.add(bc <= works[e.id, d + 1, s2.value])
                        # bc ≥ works[d][s1] + works[d+1][s2] − 1
                        model.add(bc >= works[e.id, d, s1.value] + works[e.id, d + 1, s2.value] - 1)
                        objective_terms.append(6 * bc)

        # S6 – FULLTIME_40: 6 aufeinanderfolgende Arbeitstage penalisieren (Norm: 5)
        # streak6[e,d] = 1 genau dann wenn e an den Tagen d..d+5 alle 6 arbeitet.
        for e in employees:
            if e.contract_type == ContractType.FULLTIME_40.value:
                for d in range(num_days - 5):
                    streak6 = model.new_bool_var(f"s6_{e.id}_{d}")
                    # Obere Schranke: streak6 kann nur 1 sein wenn alle 6 Tage belegt
                    for i in range(6):
                        model.add(streak6 <= works_day[e.id, d + i])
                    # Untere Schranke: wenn alle 6 belegt, muss streak6 = 1 sein
                    model.add(
                        sum(works_day[e.id, d + i] for i in range(6)) - 5 <= streak6
                    )
                    objective_terms.append(5 * streak6)

        # Zielfunktion minimieren
        model.minimize(sum(objective_terms))

        # ==============================================================
        # SOLVER
        # ==============================================================
        from ortools.sat.python import cp_model
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        solver.parameters.num_search_workers = 4

        t_start = time.time()
        status_code = solver.solve(model)
        solve_time = round(time.time() - t_start, 2)

        status_map = {
            cp_model.OPTIMAL:    "OPTIMAL",
            cp_model.FEASIBLE:   "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.UNKNOWN:    "UNKNOWN",
        }
        status_str = status_map.get(status_code, "UNKNOWN")

        if status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return SchedulerResult(
                assignments=[],
                status=status_str,
                solve_time_seconds=solve_time,
                objective_value=None,
                warnings=["Kein gültiger Plan gefunden. Bitte Verfügbarkeitsregeln prüfen."],
            )

        # ==============================================================
        # ASSIGNMENTS EXTRAHIEREN
        # ==============================================================
        assignments: list[ShiftAssignment] = []
        for e in employees:
            for d, day in enumerate(self.days):
                for s in ALL_SHIFTS:
                    if solver.value(works[e.id, d, s.value]):
                        assignments.append(ShiftAssignment(
                            period_id=self.inp.period.id,
                            date=day,
                            shift_type=s.value,
                            employee_id=e.id,
                            is_manual_override=False,
                        ))

        return SchedulerResult(
            assignments=assignments,
            status=status_str,
            solve_time_seconds=solve_time,
            objective_value=int(solver.objective_value),
        )
