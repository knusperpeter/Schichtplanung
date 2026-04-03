from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from src.database.models import DailyOccupancy, PublicHoliday


class OccupancyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # DailyOccupancy
    # ------------------------------------------------------------------

    def upsert(self, occupancy: DailyOccupancy) -> DailyOccupancy:
        existing = self.session.get(DailyOccupancy, occupancy.date)
        if existing:
            existing.checkins = occupancy.checkins
            existing.checkouts = occupancy.checkouts
            existing.occupied_rooms = occupancy.occupied_rooms
            existing.occupancy_score = occupancy.occupancy_score
            existing.occupancy_level = occupancy.occupancy_level
            self.session.flush()
            return existing
        self.session.add(occupancy)
        self.session.flush()
        return occupancy

    def get_by_date(self, target_date: date) -> Optional[DailyOccupancy]:
        return self.session.get(DailyOccupancy, target_date)

    def get_range(self, start: date, end: date) -> list[DailyOccupancy]:
        return (
            self.session.query(DailyOccupancy)
            .filter(DailyOccupancy.date >= start, DailyOccupancy.date <= end)
            .order_by(DailyOccupancy.date)
            .all()
        )

    def get_occupied_rooms_on(self, target_date: date) -> int:
        """Gibt die belegten Zimmer für einen bestimmten Tag zurück (0 falls unbekannt)."""
        row = self.session.get(DailyOccupancy, target_date)
        return row.occupied_rooms if row else 0

    def get_previous_occupied_rooms(self, target_date: date) -> int:
        """
        Gibt die belegten Zimmer des Vortages zurück.
        Wird für die rollierende Berechnung benötigt.
        """
        prev = target_date - timedelta(days=1)
        return self.get_occupied_rooms_on(prev)

    # ------------------------------------------------------------------
    # PublicHoliday
    # ------------------------------------------------------------------

    def get_holidays_in_range(self, start: date, end: date) -> list[PublicHoliday]:
        return (
            self.session.query(PublicHoliday)
            .filter(PublicHoliday.date >= start, PublicHoliday.date <= end)
            .order_by(PublicHoliday.date)
            .all()
        )

    def is_public_holiday(self, target_date: date) -> bool:
        return self.session.get(PublicHoliday, target_date) is not None

    def upsert_holiday(self, holiday: PublicHoliday) -> PublicHoliday:
        existing = self.session.get(PublicHoliday, holiday.date)
        if existing:
            existing.name = holiday.name
            existing.is_regional = holiday.is_regional
            self.session.flush()
            return existing
        self.session.add(holiday)
        self.session.flush()
        return holiday
