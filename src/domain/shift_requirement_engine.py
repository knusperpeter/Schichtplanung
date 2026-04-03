"""
Berechnet den Schichtbedarf pro Tag basierend auf Hotelauslastung.

Regeln (Priorität absteigend):

  Früh (F):  immer genau 1 Person
  Nacht (N): immer genau 1 Person (nur EXPERT)
  Spät (S):  mind. 1 Person; bei BEGINNER immer 2. Person nötig
  Zwischen (Z): optional – wird zur Pflicht wenn:
      1. Belegte Zimmer >= 60 (HIGH occupancy)
      2. Nur BEGINNER für Spät verfügbar
      3. Mitarbeiter hat Stundenminus (wird im Scheduler als Soft-Constraint behandelt)
      4. Jasmin verfügbar + keine Nacht nötig (Soft-Präferenz)
"""
from dataclasses import dataclass, field
from datetime import date

from src.domain.enums import OccupancyLevel, SkillLevel, ShiftType
from src.domain.occupancy_calculator import OccupancyResult, BETWEEN_SHIFT_ROOMS_THRESHOLD


@dataclass
class DayRequirements:
    """Schichtbedarf für einen einzelnen Tag."""
    date: date
    early_count: int = 1           # immer 1
    middle_mandatory: bool = False  # True = Pflichtschicht
    middle_max: int = 1
    late_min: int = 1              # immer mind. 1
    late_max: int = 2              # max 2 bei BEGINNER-Unterstützung
    night_count: int = 1           # immer 1

    @property
    def middle_min(self) -> int:
        return 1 if self.middle_mandatory else 0

    def summary(self) -> str:
        z = "Z(Pflicht)" if self.middle_mandatory else "Z(opt.)"
        return f"F=1  {z}  S={self.late_min}–{self.late_max}  N=1"


class ShiftRequirementEngine:
    """
    Bestimmt den Schichtbedarf für jeden Tag einer Planungsperiode.
    """

    def compute(
        self,
        target_date: date,
        occupancy: OccupancyResult | None,
        available_skill_levels_for_late: list[SkillLevel] | None = None,
    ) -> DayRequirements:
        """
        Berechnet den Schichtbedarf für einen Tag.

        Args:
            target_date:                   Das zu planende Datum.
            occupancy:                     Auslastungsdaten (None = LOW angenommen).
            available_skill_levels_for_late: Skill-Level der für Spät verfügbaren MA.
                                            Wird für BEGINNER-Prüfung verwendet.

        Returns:
            DayRequirements mit allen Anforderungen für diesen Tag.
        """
        reqs = DayRequirements(date=target_date)

        if occupancy is None:
            return reqs  # Standardfall LOW: 1F, 0Z, 1S, 1N

        # Zwischenschicht Pflicht bei hoher Auslastung (>= 60 Zimmer)
        if occupancy.requires_between_shift:
            reqs.middle_mandatory = True

        # Zwischenschicht Pflicht wenn nur BEGINNER für Spät verfügbar
        if available_skill_levels_for_late:
            only_beginners = all(
                sl == SkillLevel.BEGINNER
                for sl in available_skill_levels_for_late
            )
            if only_beginners and available_skill_levels_for_late:
                reqs.middle_mandatory = True

        # Spät max=2 wenn BEGINNER in Pool (braucht immer 2. Person)
        if available_skill_levels_for_late and any(
            sl == SkillLevel.BEGINNER for sl in available_skill_levels_for_late
        ):
            reqs.late_max = 2

        return reqs

    def compute_for_period(
        self,
        days: list[date],
        occupancy_map: dict[date, OccupancyResult],
    ) -> dict[date, DayRequirements]:
        """Berechnet den Schichtbedarf für alle Tage einer Periode."""
        return {
            day: self.compute(day, occupancy_map.get(day))
            for day in days
        }
