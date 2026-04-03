"""
EmployeeService: Business-Logik rund um Mitarbeiter.

Enthält außerdem die Seed-Funktion, die alle 8 Mitarbeiter
mit ihren Verfügbarkeitsregeln in die Datenbank schreibt.
"""
from datetime import date

from sqlalchemy.orm import Session

from src.database.models import Employee, AvailabilityRule, VacationBalance, PublicHoliday
from src.domain.enums import (
    ContractType, SkillLevel, RuleType, RuleScope, ShiftType,
    MONDAY, TUESDAY, WEDNESDAY, SUNDAY,
)
from src.repositories.employee_repository import EmployeeRepository
from src.repositories.plan_repository import PlanRepository
from src.data.bavarian_holidays import get_bavarian_holidays


# Gesetzlicher Mindesturlaub nach BUrlG (24 Werktage = 20 Arbeitstage bei 5-Tage-Woche)
DEFAULT_VACATION_DAYS_FULLTIME = 24
DEFAULT_VACATION_DAYS_PART_TIME = 20
DEFAULT_VACATION_DAYS_MINIJOB = 12


class EmployeeService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = EmployeeRepository(session)
        self.plan_repo = PlanRepository(session)

    def create_employee(
        self,
        name: str,
        skill_level: SkillLevel,
        contract_type: ContractType,
        prefers_between_shift: bool = False,
        max_late_shifts_per_week: int | None = None,
        target_hours_per_month: float | None = None,
    ) -> Employee:
        employee = Employee(
            name=name,
            skill_level=skill_level.value,
            contract_type=contract_type.value,
            target_hours_per_month=(
                target_hours_per_month
                if target_hours_per_month is not None
                else contract_type.monthly_target_hours
            ),
            prefers_between_shift=prefers_between_shift,
            max_late_shifts_per_week=max_late_shifts_per_week,
        )
        return self.repo.create(employee)

    def add_blocked_shift(self, employee_id: int, shift_type: ShiftType, note: str = "") -> AvailabilityRule:
        rule = AvailabilityRule(
            employee_id=employee_id,
            rule_type=RuleType.BLOCKED.value,
            scope=RuleScope.SHIFT_TYPE.value,
            shift_type=shift_type.value,
            note=note or f"Kann keine {shift_type.label} arbeiten",
        )
        return self.repo.add_rule(rule)

    def add_blocked_day(self, employee_id: int, day_of_week: int, note: str = "") -> AvailabilityRule:
        day_names = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
        rule = AvailabilityRule(
            employee_id=employee_id,
            rule_type=RuleType.BLOCKED.value,
            scope=RuleScope.DAY_OF_WEEK.value,
            day_of_week=day_of_week,
            note=note or f"Kann nicht {day_names[day_of_week]}s arbeiten",
        )
        return self.repo.add_rule(rule)

    def add_blocked_day_and_shift(
        self, employee_id: int, day_of_week: int, shift_type: ShiftType, note: str = ""
    ) -> AvailabilityRule:
        day_names = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
        rule = AvailabilityRule(
            employee_id=employee_id,
            rule_type=RuleType.BLOCKED.value,
            scope=RuleScope.DAY_AND_SHIFT.value,
            day_of_week=day_of_week,
            shift_type=shift_type.value,
            note=note or f"Kein {shift_type.label} am {day_names[day_of_week]}",
        )
        return self.repo.add_rule(rule)

    def add_preferred_shift(self, employee_id: int, shift_type: ShiftType, note: str = "") -> AvailabilityRule:
        rule = AvailabilityRule(
            employee_id=employee_id,
            rule_type=RuleType.PREFERRED.value,
            scope=RuleScope.SHIFT_TYPE.value,
            shift_type=shift_type.value,
            note=note or f"Bevorzugt {shift_type.label}",
        )
        return self.repo.add_rule(rule)

    def add_avoid_day(self, employee_id: int, day_of_week: int, note: str = "") -> AvailabilityRule:
        day_names = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
        rule = AvailabilityRule(
            employee_id=employee_id,
            rule_type=RuleType.AVOID.value,
            scope=RuleScope.DAY_OF_WEEK.value,
            day_of_week=day_of_week,
            note=note or f"Meidet {day_names[day_of_week]}",
        )
        return self.repo.add_rule(rule)

    def add_vacation_day(self, employee_id: int, vacation_date: date) -> AvailabilityRule:
        rule = AvailabilityRule(
            employee_id=employee_id,
            rule_type=RuleType.VACATION.value,
            scope=RuleScope.SPECIFIC_DATE.value,
            specific_date=vacation_date,
            note="Urlaubstag",
        )
        return self.repo.add_rule(rule)

    def init_vacation_balance(
        self, employee_id: int, year: int, entitlement_days: int
    ) -> VacationBalance:
        balance = VacationBalance(
            employee_id=employee_id,
            year=year,
            entitlement_days=entitlement_days,
            used_days=0,
            remaining_days=entitlement_days,
        )
        return self.plan_repo.upsert_vacation_balance(balance)

    def get_all_employees(self) -> list[Employee]:
        return self.repo.get_all()

    def seed_holidays(self, year: int) -> int:
        """Schreibt bayerische Feiertage für das angegebene Jahr in die DB."""
        count = 0
        for holiday_date, name, is_regional in get_bavarian_holidays(year):
            existing = self.session.get(PublicHoliday, holiday_date)
            if not existing:
                self.session.add(PublicHoliday(
                    date=holiday_date,
                    name=name,
                    is_regional=is_regional,
                ))
                count += 1
        self.session.flush()
        return count


def seed_employees(session: Session) -> None:
    """
    Legt alle 8 Mitarbeiter mit ihren Verfügbarkeitsregeln an,
    falls sie noch nicht existieren.
    """
    service = EmployeeService(session)
    repo = EmployeeRepository(session)

    def _get_or_create(
        name: str,
        skill: SkillLevel,
        contract: ContractType,
        prefers_between: bool = False,
        max_late: int | None = None,
    ) -> tuple[Employee, bool]:
        existing = repo.get_by_name(name)
        if existing:
            return existing, False
        emp = service.create_employee(
            name=name,
            skill_level=skill,
            contract_type=contract,
            prefers_between_shift=prefers_between,
            max_late_shifts_per_week=max_late,
        )
        return emp, True

    # ------------------------------------------------------------------
    # Allen – extrem erfahren, Vollzeit 40h
    # Kann NICHT: Früh, Zwischen  |  Präferenz: Nacht
    # ------------------------------------------------------------------
    allen, created = _get_or_create("Allen", SkillLevel.EXPERT, ContractType.FULLTIME_40)
    if created:
        service.add_blocked_shift(allen.id, ShiftType.EARLY)
        service.add_blocked_shift(allen.id, ShiftType.MIDDLE)
        service.add_preferred_shift(allen.id, ShiftType.NIGHT)

    # ------------------------------------------------------------------
    # Simon – extrem erfahren, Vollzeit 40h
    # Kann NICHT: Früh, Zwischen, max 2× Spät/Woche  |  Präferenz: Nacht (stark)
    # ------------------------------------------------------------------
    simon, created = _get_or_create(
        "Simon", SkillLevel.EXPERT, ContractType.FULLTIME_40, max_late=2
    )
    if created:
        service.add_blocked_shift(simon.id, ShiftType.EARLY)
        service.add_blocked_shift(simon.id, ShiftType.MIDDLE)
        service.add_preferred_shift(simon.id, ShiftType.NIGHT, note="Starke Präferenz: Nachtschicht")

    # ------------------------------------------------------------------
    # Jasmin – extrem erfahren, Vollzeit 40h
    # Kann NICHT: Mittwochs  |  Starke Präferenz: Zwischen
    # ------------------------------------------------------------------
    jasmin, created = _get_or_create(
        "Jasmin", SkillLevel.EXPERT, ContractType.FULLTIME_40, prefers_between=True
    )
    if created:
        service.add_blocked_day(jasmin.id, WEDNESDAY)
        service.add_preferred_shift(jasmin.id, ShiftType.MIDDLE, note="Starke Präferenz: Zwischenschicht")

    # ------------------------------------------------------------------
    # Benze – mittelmäßig erfahren, Vollzeit 40h
    # Kann NICHT: Nacht, Früh-Sonntag  |  Präferenz: kein Sonntag
    # ------------------------------------------------------------------
    benze, created = _get_or_create("Benze", SkillLevel.MEDIUM, ContractType.FULLTIME_40)
    if created:
        service.add_blocked_shift(benze.id, ShiftType.NIGHT)
        service.add_blocked_day_and_shift(benze.id, SUNDAY, ShiftType.EARLY)
        service.add_avoid_day(benze.id, SUNDAY, note="Präferenz: kein Sonntag")

    # ------------------------------------------------------------------
    # Ilgar – nichtskönner, Vollzeit 40h
    # Kann NICHT: Nacht  |  Spät nur mit 2. Person (wird durch Skill-Level geregelt)
    # ------------------------------------------------------------------
    ilgar, created = _get_or_create("Ilgar", SkillLevel.BEGINNER, ContractType.FULLTIME_40)
    if created:
        service.add_blocked_shift(ilgar.id, ShiftType.NIGHT)

    # ------------------------------------------------------------------
    # Pia – extrem erfahren, Mindeststunden 24h/Woche
    # Kann NUR: Früh  (Spät und Nacht blockiert)
    # ------------------------------------------------------------------
    pia, created = _get_or_create("Pia", SkillLevel.EXPERT, ContractType.MIN_24)
    if created:
        service.add_blocked_shift(pia.id, ShiftType.MIDDLE)
        service.add_blocked_shift(pia.id, ShiftType.LATE)
        service.add_blocked_shift(pia.id, ShiftType.NIGHT)

    # ------------------------------------------------------------------
    # Dimitri – nichtskönner, max 20h/Woche
    # Kann NICHT: Nacht, Mo/Di/Mi  |  Bestenfalls Früh + Zwischen
    # ------------------------------------------------------------------
    dimitri, created = _get_or_create("Dimitri", SkillLevel.BEGINNER, ContractType.MAX_20)
    if created:
        service.add_blocked_shift(dimitri.id, ShiftType.NIGHT)
        service.add_blocked_shift(dimitri.id, ShiftType.LATE, note="Bestenfalls nur Früh und Zwischen")
        service.add_blocked_day(dimitri.id, MONDAY)
        service.add_blocked_day(dimitri.id, TUESDAY)
        service.add_blocked_day(dimitri.id, WEDNESDAY)

    # ------------------------------------------------------------------
    # Lena – mittelmäßig erfahren, Minijob ~10h/Woche
    # Kann NICHT: Nacht, Spät  |  Nur Wochenende (Sa/So)
    # ------------------------------------------------------------------
    lena, created = _get_or_create("Lena", SkillLevel.MEDIUM, ContractType.MINIJOB)
    if created:
        service.add_blocked_shift(lena.id, ShiftType.NIGHT)
        service.add_blocked_shift(lena.id, ShiftType.LATE, note="Bestenfalls nur Früh und Zwischen")
        # Alle Wochentage Mo–Fr blockieren (nur Sa/So erlaubt)
        for weekday in [MONDAY, TUESDAY, WEDNESDAY, 3, 4]:  # 3=Do, 4=Fr
            service.add_blocked_day(lena.id, weekday)

    session.flush()
    print("Mitarbeiter erfolgreich angelegt.")
