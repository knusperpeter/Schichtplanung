from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from src.database.models import PlanningPeriod, ShiftAssignment, HourBalance, VacationBalance
from src.domain.enums import PlanStatus, ShiftType


class PlanRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # PlanningPeriod
    # ------------------------------------------------------------------

    def create_period(self, period: PlanningPeriod) -> PlanningPeriod:
        self.session.add(period)
        self.session.flush()
        return period

    def get_period_by_id(self, period_id: int) -> Optional[PlanningPeriod]:
        return self.session.get(PlanningPeriod, period_id)

    def get_all_periods(self) -> list[PlanningPeriod]:
        return (
            self.session.query(PlanningPeriod)
            .order_by(PlanningPeriod.start_date.desc())
            .all()
        )

    def get_period_for_date(self, target_date: date) -> Optional[PlanningPeriod]:
        return (
            self.session.query(PlanningPeriod)
            .filter(
                PlanningPeriod.start_date <= target_date,
                PlanningPeriod.end_date >= target_date,
            )
            .first()
        )

    def update_period_status(self, period_id: int, status: PlanStatus) -> None:
        period = self.session.get(PlanningPeriod, period_id)
        if period:
            period.status = status.value
            self.session.flush()

    def delete_period(self, period: PlanningPeriod) -> None:
        self.session.delete(period)
        self.session.flush()

    # ------------------------------------------------------------------
    # ShiftAssignment
    # ------------------------------------------------------------------

    def add_assignment(self, assignment: ShiftAssignment) -> ShiftAssignment:
        self.session.add(assignment)
        self.session.flush()
        return assignment

    def get_assignments_for_period(self, period_id: int) -> list[ShiftAssignment]:
        return (
            self.session.query(ShiftAssignment)
            .filter_by(period_id=period_id)
            .order_by(ShiftAssignment.date, ShiftAssignment.shift_type)
            .all()
        )

    def get_assignments_for_employee_in_period(
        self, employee_id: int, period_id: int
    ) -> list[ShiftAssignment]:
        return (
            self.session.query(ShiftAssignment)
            .filter_by(employee_id=employee_id, period_id=period_id)
            .order_by(ShiftAssignment.date)
            .all()
        )

    def get_assignments_on_date(
        self, target_date: date, period_id: int
    ) -> list[ShiftAssignment]:
        return (
            self.session.query(ShiftAssignment)
            .filter_by(date=target_date, period_id=period_id)
            .all()
        )

    def get_assignments_on_date_and_shift(
        self, target_date: date, shift_type: ShiftType, period_id: int
    ) -> list[ShiftAssignment]:
        return (
            self.session.query(ShiftAssignment)
            .filter_by(date=target_date, shift_type=shift_type.value, period_id=period_id)
            .all()
        )

    def delete_all_assignments_for_period(self, period_id: int) -> None:
        self.session.query(ShiftAssignment).filter_by(period_id=period_id).delete()
        self.session.flush()

    def delete_assignment(self, assignment: ShiftAssignment) -> None:
        self.session.delete(assignment)
        self.session.flush()

    # ------------------------------------------------------------------
    # HourBalance
    # ------------------------------------------------------------------

    def upsert_hour_balance(self, balance: HourBalance) -> HourBalance:
        existing = (
            self.session.query(HourBalance)
            .filter_by(
                employee_id=balance.employee_id,
                year=balance.year,
                month=balance.month,
            )
            .first()
        )
        if existing:
            existing.target_hours = balance.target_hours
            existing.scheduled_hours = balance.scheduled_hours
            existing.holiday_bonus_hours = balance.holiday_bonus_hours
            existing.vacation_hours = balance.vacation_hours
            existing.balance_delta = balance.balance_delta
            existing.cumulative_balance = balance.cumulative_balance
            self.session.flush()
            return existing
        self.session.add(balance)
        self.session.flush()
        return balance

    def get_hour_balance(
        self, employee_id: int, year: int, month: int
    ) -> Optional[HourBalance]:
        return (
            self.session.query(HourBalance)
            .filter_by(employee_id=employee_id, year=year, month=month)
            .first()
        )

    def get_hour_balances_for_employee(self, employee_id: int) -> list[HourBalance]:
        return (
            self.session.query(HourBalance)
            .filter_by(employee_id=employee_id)
            .order_by(HourBalance.year, HourBalance.month)
            .all()
        )

    def get_cumulative_balance(self, employee_id: int, year: int, month: int) -> float:
        """Gibt den kumulativen Stundenstand bis einschließlich angegebenen Monat zurück."""
        balance = self.get_hour_balance(employee_id, year, month)
        return balance.cumulative_balance if balance else 0.0

    # ------------------------------------------------------------------
    # VacationBalance
    # ------------------------------------------------------------------

    def upsert_vacation_balance(self, balance: VacationBalance) -> VacationBalance:
        existing = (
            self.session.query(VacationBalance)
            .filter_by(employee_id=balance.employee_id, year=balance.year)
            .first()
        )
        if existing:
            existing.entitlement_days = balance.entitlement_days
            existing.used_days = balance.used_days
            existing.remaining_days = balance.remaining_days
            self.session.flush()
            return existing
        self.session.add(balance)
        self.session.flush()
        return balance

    def get_vacation_balance(
        self, employee_id: int, year: int
    ) -> Optional[VacationBalance]:
        return (
            self.session.query(VacationBalance)
            .filter_by(employee_id=employee_id, year=year)
            .first()
        )
