"""
Berechnung der Hotelbelegung und des Auslastungs-Scores.

Rollierendes Modell:
    occupied_rooms(t) = occupied_rooms(t-1) + checkins(t) − checkouts(t)

Gewichteter Score:
    score = 0.5 × checkins + 0.3 × occupied_rooms + 0.2 × checkouts

Auslastungsstufen:
    LOW    score < 40   → keine Zwischenschicht nötig
    MEDIUM score 40–60  → Zwischenschicht bei Skill-Bedarf
    HIGH   score > 60   → Zwischenschicht immer Pflicht
"""
from dataclasses import dataclass
from datetime import date, timedelta

from src.domain.enums import OccupancyLevel

# Gewichte für den Score (absteigend nach Bedeutung)
WEIGHT_CHECKINS = 0.5
WEIGHT_OCCUPIED = 0.3
WEIGHT_CHECKOUTS = 0.2

LEVEL_HIGH_THRESHOLD = 60.0
LEVEL_MEDIUM_THRESHOLD = 40.0

# Ab dieser Zimmeranzahl ist Zwischenschicht immer Pflicht
BETWEEN_SHIFT_ROOMS_THRESHOLD = 60


@dataclass
class OccupancyResult:
    date: date
    checkins: int
    checkouts: int
    occupied_rooms: int
    occupancy_score: float
    occupancy_level: OccupancyLevel

    @property
    def requires_between_shift(self) -> bool:
        """True wenn die Belegungsregeln eine Zwischenschicht vorschreiben."""
        return self.occupied_rooms >= BETWEEN_SHIFT_ROOMS_THRESHOLD

    @property
    def level_label(self) -> str:
        return {
            OccupancyLevel.LOW: "Niedrig",
            OccupancyLevel.MEDIUM: "Mittel",
            OccupancyLevel.HIGH: "Hoch",
        }[self.occupancy_level]


def calculate_score(checkins: int, occupied: int, checkouts: int) -> float:
    return (
        WEIGHT_CHECKINS * checkins
        + WEIGHT_OCCUPIED * occupied
        + WEIGHT_CHECKOUTS * checkouts
    )


def classify_level(score: float) -> OccupancyLevel:
    if score > LEVEL_HIGH_THRESHOLD:
        return OccupancyLevel.HIGH
    if score >= LEVEL_MEDIUM_THRESHOLD:
        return OccupancyLevel.MEDIUM
    return OccupancyLevel.LOW


def calculate_occupancy(
    target_date: date,
    checkins: int,
    checkouts: int,
    previous_occupied: int,
) -> OccupancyResult:
    """
    Berechnet die Belegung für einen einzelnen Tag.

    Args:
        target_date:       Das Datum.
        checkins:          Anzahl eincheckender Zimmer.
        checkouts:         Anzahl abreisender Personen.
        previous_occupied: Belegte Zimmer am Vortag.
    """
    occupied = max(0, previous_occupied + checkins - checkouts)
    score = calculate_score(checkins, occupied, checkouts)
    level = classify_level(score)
    return OccupancyResult(
        date=target_date,
        checkins=checkins,
        checkouts=checkouts,
        occupied_rooms=occupied,
        occupancy_score=round(score, 2),
        occupancy_level=level,
    )


def calculate_occupancy_range(
    entries: list[tuple[date, int, int]],
    initial_occupied: int = 0,
) -> list[OccupancyResult]:
    """
    Berechnet die Belegung für eine Folge von Tagen rollierend.

    Args:
        entries:          Liste von (datum, checkins, checkouts), aufsteigend sortiert.
        initial_occupied: Belegte Zimmer vor dem ersten Tag der Liste.

    Returns:
        Liste von OccupancyResult in der gleichen Reihenfolge wie entries.
    """
    results: list[OccupancyResult] = []
    prev_occupied = initial_occupied

    for target_date, checkins, checkouts in sorted(entries, key=lambda x: x[0]):
        result = calculate_occupancy(target_date, checkins, checkouts, prev_occupied)
        results.append(result)
        prev_occupied = result.occupied_rooms

    return results
