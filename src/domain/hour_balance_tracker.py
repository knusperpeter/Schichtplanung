"""
Monatliches Stundenkonto-Management.

Logik:
  - Zielstunden für eine Periode = proportionaler Anteil des Monatsziels
  - Überstunden = tatsächliche - Ziel → auf Folgemonat übertragen
  - Urlaubstage zählen als gearbeitete Stunden (BUrlG)
  - Feiertagsarbeit = geplante Stunden + Feiertagsbonus
  - Keine Obergrenze; kein automatischer Reset; Jahresübertrag erlaubt
  - Jahresend-Warnung wenn Kumulativstand > 0 (Überstunden abbauen!)
"""
from calendar import monthrange
from collections import defaultdict
from datetime import date

from src.database.models import Employee, ShiftAssignment, HourBalance
from src.domain.enums import RuleType
from src.data.bavarian_holidays import get_holiday_dates

HOURS_PER_SHIFT = 8.5
YEAR_END_WARNING_MONTH = 10   # ab Oktober warnen


class HourBalanceTracker:

    # ------------------------------------------------------------------
    # Zielberechnung für eine Planungsperiode
    # ------------------------------------------------------------------

    def period_target_hours(
        self,
        employee: Employee,
        start_date: date,
        end_date: date,
    ) -> float:
        """
        Proportionaler Stunden-Anteil des Monatsziels für die Planungsperiode.
        Berücksichtigt Monatsübergänge (z.B. 26. März – 8. April).
        """
        total = 0.0
        current = start_date

        while current <= end_date:
            year, month = current.year, current.month
            days_in_month = monthrange(year, month)[1]
            # Letzter Tag dieser Monatsscheibe in der Periode
            last_of_month = date(year, month, days_in_month)
            slice_end = min(end_date, last_of_month)
            slice_days = (slice_end - current).days + 1

            daily_target = employee.target_hours_per_month / days_in_month
            total += daily_target * slice_days

            # Zum nächsten Monatsersten springen
            if month == 12:
                current = date(year + 1, 1, 1)
            else:
                current = date(year, month + 1, 1)

        return round(total, 4)

    def period_target_shifts(
        self,
        employee: Employee,
        start_date: date,
        end_date: date,
    ) -> int:
        """Zielschichten für die Periode (gerundet)."""
        return round(self.period_target_hours(employee, start_date, end_date) / HOURS_PER_SHIFT)

    # ------------------------------------------------------------------
    # Stundenkonten nach Planung aktualisieren
    # ------------------------------------------------------------------

    def update_balances(
        self,
        session,
        assignments: list[ShiftAssignment],
        employees: list[Employee],
    ) -> list[HourBalance]:
        """
        Berechnet und persistiert die monatlichen Stundenkonten
        für alle betroffenen Mitarbeiter.

        Gibt die aktualisierten HourBalance-Objekte zurück.
        """
        from src.repositories.plan_repository import PlanRepository
        plan_repo = PlanRepository(session)

        # Feiertagssets nach Jahr cachen
        holiday_cache: dict[int, set[date]] = {}

        # assignments gruppiert: emp_id → {(year, month): [ShiftAssignment]}
        emp_month: dict[int, dict[tuple[int, int], list[ShiftAssignment]]] = defaultdict(lambda: defaultdict(list))
        for a in assignments:
            emp_month[a.employee_id][(a.date.year, a.date.month)].append(a)

        updated: list[HourBalance] = []

        for emp in employees:
            for (year, month), month_assignments in emp_month[emp.id].items():

                if year not in holiday_cache:
                    holiday_cache[year] = get_holiday_dates(year)
                holidays = holiday_cache[year]

                days_in_month = monthrange(year, month)[1]

                # Tatsächlich geplante Schichtstunden
                scheduled_hours = len(month_assignments) * HOURS_PER_SHIFT

                # Feiertagsbonus: jede Schicht an einem Feiertag zählt extra
                holiday_bonus = sum(
                    HOURS_PER_SHIFT
                    for a in month_assignments
                    if a.date in holidays
                )

                # Urlaubsstunden: Urlaubstage zählen als tägliche Ø-Arbeitszeit
                daily_target = emp.target_hours_per_month / days_in_month
                vacation_days_this_month = [
                    rule.specific_date
                    for rule in emp.availability_rules
                    if rule.rule_type == RuleType.VACATION.value
                    and rule.specific_date
                    and rule.specific_date.year == year
                    and rule.specific_date.month == month
                ]
                vacation_hours = len(vacation_days_this_month) * daily_target

                # Delta: (gearbeitet + Urlaub) – Ziel
                balance_delta = round(
                    (scheduled_hours + vacation_hours) - emp.target_hours_per_month,
                    2,
                )

                # Kumulativstand: Vormonat holen
                prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
                prev_cumulative = plan_repo.get_cumulative_balance(emp.id, prev_year, prev_month)
                cumulative = round(prev_cumulative + balance_delta, 2)

                balance = HourBalance(
                    employee_id=emp.id,
                    year=year,
                    month=month,
                    target_hours=emp.target_hours_per_month,
                    scheduled_hours=scheduled_hours,
                    holiday_bonus_hours=holiday_bonus,
                    vacation_hours=round(vacation_hours, 2),
                    balance_delta=balance_delta,
                    cumulative_balance=cumulative,
                )
                updated.append(plan_repo.upsert_hour_balance(balance))

        return updated

    # ------------------------------------------------------------------
    # Warnungen
    # ------------------------------------------------------------------

    def year_end_warnings(
        self,
        session,
        employees: list[Employee],
        reference_date: date,
    ) -> list[str]:
        """
        Gibt Warnungen aus wenn Mitarbeiter > 0h Kumulativstand haben
        und wir uns im letzten Quartal des Jahres befinden.
        """
        if reference_date.month < YEAR_END_WARNING_MONTH:
            return []

        from src.repositories.plan_repository import PlanRepository
        plan_repo = PlanRepository(session)
        warnings = []

        for emp in employees:
            balance = plan_repo.get_hour_balance(
                emp.id, reference_date.year, reference_date.month
            )
            if balance and balance.cumulative_balance > 0:
                warnings.append(
                    f"{emp.name}: +{balance.cumulative_balance:.1f}h Überstunden – "
                    f"bis Jahresende abbauen (kein Reset zum Neujahr)."
                )
        return warnings
