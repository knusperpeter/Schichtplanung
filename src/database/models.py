from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    skill_level: Mapped[str] = mapped_column(String(20), nullable=False)        # SkillLevel
    contract_type: Mapped[str] = mapped_column(String(20), nullable=False)      # ContractType
    target_hours_per_month: Mapped[float] = mapped_column(Float, nullable=False)
    prefers_between_shift: Mapped[bool] = mapped_column(Boolean, default=False)
    max_late_shifts_per_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    availability_rules: Mapped[list["AvailabilityRule"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan", lazy="select"
    )
    hour_balances: Mapped[list["HourBalance"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan", lazy="select"
    )
    vacation_balances: Mapped[list["VacationBalance"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan", lazy="select"
    )
    shift_assignments: Mapped[list["ShiftAssignment"]] = relationship(
        back_populates="employee", lazy="select"
    )
    overtime_entries: Mapped[list["OvertimeEntry"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Employee {self.name} ({self.skill_level}, {self.contract_type})>"


class AvailabilityRule(Base):
    """
    Verfügbarkeitsregel eines Mitarbeiters.

    Beispiele:
        BLOCKED  / SHIFT_TYPE   / shift_type=N          → darf nie Nachtschicht
        BLOCKED  / DAY_OF_WEEK  / day_of_week=2          → nie Mittwochs
        BLOCKED  / DAY_AND_SHIFT/ day_of_week=6, shift=F → nie Früh am Sonntag
        PREFERRED/ SHIFT_TYPE   / shift_type=N          → bevorzugt Nacht
        VACATION / SPECIFIC_DATE/ specific_date=...     → Urlaubstag
    """
    __tablename__ = "availability_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(20), nullable=False)   # RuleType
    scope: Mapped[str] = mapped_column(String(20), nullable=False)        # RuleScope
    shift_type: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)   # ShiftType.value
    day_of_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)    # 0=Mo … 6=So
    specific_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    employee: Mapped["Employee"] = relationship(back_populates="availability_rules")

    def __repr__(self) -> str:
        return (
            f"<AvailabilityRule {self.rule_type}/{self.scope} "
            f"shift={self.shift_type} dow={self.day_of_week} date={self.specific_date}>"
        )


class DailyOccupancy(Base):
    """
    Hotelbelegung pro Tag.
    occupied_rooms und occupancy_score werden bei der Eingabe berechnet und gespeichert.
    """
    __tablename__ = "daily_occupancy"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    checkins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checkouts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Rollierend berechnet: Vortag + checkins − checkouts
    occupied_rooms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Gewichteter Score: 0.5*checkins + 0.3*occupied + 0.2*checkouts
    occupancy_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    occupancy_level: Mapped[str] = mapped_column(String(10), nullable=False, default="LOW")  # OccupancyLevel

    def __repr__(self) -> str:
        return (
            f"<DailyOccupancy {self.date} "
            f"in={self.checkins} out={self.checkouts} "
            f"occ={self.occupied_rooms} [{self.occupancy_level}]>"
        )


class PlanningPeriod(Base):
    """2-Wochen-Planungsperiode."""
    __tablename__ = "planning_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")  # PlanStatus
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    shift_assignments: Mapped[list["ShiftAssignment"]] = relationship(
        back_populates="period", cascade="all, delete-orphan", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<PlanningPeriod {self.start_date} – {self.end_date} [{self.status}]>"


class ShiftAssignment(Base):
    """Zuweisung eines Mitarbeiters zu einer Schicht an einem Tag."""
    __tablename__ = "shift_assignments"
    __table_args__ = (
        UniqueConstraint("period_id", "date", "shift_type", "employee_id",
                         name="uq_assignment"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("planning_periods.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    shift_type: Mapped[str] = mapped_column(String(1), nullable=False)   # ShiftType.value
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    is_manual_override: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    period: Mapped["PlanningPeriod"] = relationship(back_populates="shift_assignments")
    employee: Mapped["Employee"] = relationship(back_populates="shift_assignments")

    def __repr__(self) -> str:
        return f"<ShiftAssignment {self.date} {self.shift_type} → {self.employee_id}>"


class HourBalance(Base):
    """Monatliches Stundenkonto eines Mitarbeiters."""
    __tablename__ = "hour_balances"
    __table_args__ = (
        UniqueConstraint("employee_id", "year", "month", name="uq_hour_balance"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    target_hours: Mapped[float] = mapped_column(Float, nullable=False)
    scheduled_hours: Mapped[float] = mapped_column(Float, default=0.0)
    holiday_bonus_hours: Mapped[float] = mapped_column(Float, default=0.0)  # Feiertagszuschlag
    vacation_hours: Mapped[float] = mapped_column(Float, default=0.0)       # zählen als gearbeitet
    # balance_delta = scheduled_hours + vacation_hours − target_hours
    balance_delta: Mapped[float] = mapped_column(Float, default=0.0)
    # Laufendes Gesamtkonto (Übertrag aus Vormonat + balance_delta)
    cumulative_balance: Mapped[float] = mapped_column(Float, default=0.0)

    employee: Mapped["Employee"] = relationship(back_populates="hour_balances")

    def __repr__(self) -> str:
        return (
            f"<HourBalance {self.employee_id} {self.year}/{self.month:02d} "
            f"delta={self.balance_delta:+.1f}h cumul={self.cumulative_balance:+.1f}h>"
        )


class PublicHoliday(Base):
    """Bayerische Feiertage (statisch gepflegt)."""
    __tablename__ = "public_holidays"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Regionaler Feiertag (z.B. Mariä Himmelfahrt – nur in bestimmten Gemeinden)
    is_regional: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        tag = " (regional)" if self.is_regional else ""
        return f"<PublicHoliday {self.date} {self.name}{tag}>"


class VacationBalance(Base):
    """Jahresurlaubskonto eines Mitarbeiters."""
    __tablename__ = "vacation_balances"
    __table_args__ = (
        UniqueConstraint("employee_id", "year", name="uq_vacation_balance"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    entitlement_days: Mapped[int] = mapped_column(Integer, nullable=False)  # Jahresanspruch
    used_days: Mapped[int] = mapped_column(Integer, default=0)
    remaining_days: Mapped[int] = mapped_column(Integer, nullable=False)    # entitlement − used

    employee: Mapped["Employee"] = relationship(back_populates="vacation_balances")

    def __repr__(self) -> str:
        return (
            f"<VacationBalance {self.employee_id} {self.year}: "
            f"{self.used_days}/{self.entitlement_days} Tage verbraucht>"
        )


class OvertimeEntry(Base):
    """Manueller Eintrag im Überstundenkonto eines Mitarbeiters (Plus- oder Minusstunden)."""
    __tablename__ = "overtime_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Positive Werte = Überstunden, negative Werte = Freizeitausgleich / Abzug
    hours: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    employee: Mapped["Employee"] = relationship(back_populates="overtime_entries")

    def __repr__(self) -> str:
        return f"<OvertimeEntry {self.employee_id} {self.entry_date} {self.hours:+.2f}h>"
