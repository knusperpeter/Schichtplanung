from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from src.database.models import Employee, AvailabilityRule, OvertimeEntry
from src.domain.enums import RuleType, RuleScope, ShiftType


class EmployeeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Employee CRUD
    # ------------------------------------------------------------------

    def create(self, employee: Employee) -> Employee:
        self.session.add(employee)
        self.session.flush()
        return employee

    def get_by_id(self, employee_id: int) -> Optional[Employee]:
        return self.session.get(Employee, employee_id)

    def get_by_name(self, name: str) -> Optional[Employee]:
        return self.session.query(Employee).filter_by(name=name).first()

    def get_all(self) -> list[Employee]:
        from sqlalchemy.orm import selectinload
        return (
            self.session.query(Employee)
            .options(selectinload(Employee.availability_rules))
            .order_by(Employee.name)
            .all()
        )

    def update(self, employee: Employee) -> Employee:
        self.session.flush()
        return employee

    def delete(self, employee: Employee) -> None:
        self.session.delete(employee)
        self.session.flush()

    # ------------------------------------------------------------------
    # AvailabilityRule CRUD
    # ------------------------------------------------------------------

    def add_rule(self, rule: AvailabilityRule) -> AvailabilityRule:
        self.session.add(rule)
        self.session.flush()
        return rule

    def get_rules_for_employee(self, employee_id: int) -> list[AvailabilityRule]:
        return (
            self.session.query(AvailabilityRule)
            .filter_by(employee_id=employee_id)
            .all()
        )

    def delete_rule(self, rule: AvailabilityRule) -> None:
        self.session.delete(rule)
        self.session.flush()

    def delete_all_rules_for_employee(self, employee_id: int) -> None:
        self.session.query(AvailabilityRule).filter_by(employee_id=employee_id).delete()
        self.session.flush()

    # ------------------------------------------------------------------
    # Abfragen für den Scheduler
    # ------------------------------------------------------------------

    def is_blocked(
        self,
        employee_id: int,
        target_date: date,
        shift_type: ShiftType,
    ) -> bool:
        """
        Gibt True zurück wenn der Mitarbeiter an diesem Tag/Schicht blockiert ist.
        Prüft: BLOCKED-Regeln per SPECIFIC_DATE, DAY_OF_WEEK, SHIFT_TYPE, DAY_AND_SHIFT.
        """
        rules = self.get_rules_for_employee(employee_id)
        dow = target_date.weekday()  # 0=Montag

        for rule in rules:
            if rule.rule_type not in (RuleType.BLOCKED, RuleType.VACATION, RuleType.SICK):
                continue
            match rule.scope:
                case RuleScope.SPECIFIC_DATE:
                    if rule.specific_date == target_date:
                        return True
                case RuleScope.DAY_OF_WEEK:
                    if rule.day_of_week == dow:
                        return True
                case RuleScope.SHIFT_TYPE:
                    if rule.shift_type == shift_type.value:
                        return True
                case RuleScope.DAY_AND_SHIFT:
                    if rule.day_of_week == dow and rule.shift_type == shift_type.value:
                        return True
        return False

    def get_preferred_shifts(self, employee_id: int) -> list[ShiftType]:
        """Gibt die bevorzugten Schichttypen eines Mitarbeiters zurück."""
        rules = self.get_rules_for_employee(employee_id)
        return [
            ShiftType(r.shift_type)
            for r in rules
            if r.rule_type == RuleType.PREFERRED
            and r.scope == RuleScope.SHIFT_TYPE
            and r.shift_type is not None
        ]

    def get_vacation_days(self, employee_id: int, year: int, month: int) -> list[date]:
        """Gibt alle Urlaubstage im angegebenen Monat zurück."""
        rules = self.get_rules_for_employee(employee_id)
        return [
            r.specific_date
            for r in rules
            if r.rule_type == RuleType.VACATION
            and r.specific_date is not None
            and r.specific_date.year == year
            and r.specific_date.month == month
        ]

    # ------------------------------------------------------------------
    # OvertimeEntry CRUD
    # ------------------------------------------------------------------

    def add_overtime_entry(self, entry: OvertimeEntry) -> OvertimeEntry:
        self.session.add(entry)
        self.session.flush()
        return entry

    def get_overtime_entries(self, employee_id: int) -> list[OvertimeEntry]:
        return (
            self.session.query(OvertimeEntry)
            .filter_by(employee_id=employee_id)
            .order_by(OvertimeEntry.entry_date)
            .all()
        )

    def delete_overtime_entry(self, entry: OvertimeEntry) -> None:
        self.session.delete(entry)
        self.session.flush()

    def get_overtime_total(self, employee_id: int) -> float:
        """Gibt die Summe aller manuellen Überstunden-Einträge zurück."""
        entries = self.get_overtime_entries(employee_id)
        return sum(e.hours for e in entries)
