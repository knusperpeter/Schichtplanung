from enum import Enum


class ShiftType(str, Enum):
    EARLY = "F"    # Frühschicht  06:00–14:30
    MIDDLE = "Z"   # Zwischenschicht 10:15–18:45
    LATE = "S"     # Spätschicht  14:00–22:30
    NIGHT = "N"    # Nachtschicht 22:00–06:30

    @property
    def label(self) -> str:
        return {
            "F": "Frühschicht",
            "Z": "Zwischenschicht",
            "S": "Spätschicht",
            "N": "Nachtschicht",
        }[self.value]

    @property
    def start_time(self) -> str:
        return {"F": "06:00", "Z": "10:15", "S": "14:00", "N": "22:00"}[self.value]

    @property
    def end_time(self) -> str:
        return {"F": "14:30", "Z": "18:45", "S": "22:30", "N": "06:30"}[self.value]

    @property
    def duration_hours(self) -> float:
        return 8.5


class ShiftBlock(str, Enum):
    """Gruppierung von Schichten für Ruhezeit-Prüfung."""
    MORNING = "MORNING"   # F, Z
    EVENING = "EVENING"   # S
    NIGHT = "NIGHT"       # N

    @staticmethod
    def from_shift(shift: ShiftType) -> "ShiftBlock":
        if shift in (ShiftType.EARLY, ShiftType.MIDDLE):
            return ShiftBlock.MORNING
        if shift == ShiftType.LATE:
            return ShiftBlock.EVENING
        return ShiftBlock.NIGHT


class SkillLevel(str, Enum):
    EXPERT = "EXPERT"       # extrem erfahren – kann Spät alleine bei jeder Auslastung
    MEDIUM = "MEDIUM"       # mittelmäßig erfahren
    BEGINNER = "BEGINNER"   # nichtskönner – braucht immer 2. Person bei Spät


class ContractType(str, Enum):
    FULLTIME_40 = "FULLTIME_40"   # 40 h/Woche  → ~173,3 h/Monat
    MIN_24 = "MIN_24"             # mind. 24 h/Woche → ~104 h/Monat
    MAX_20 = "MAX_20"             # max. 20 h/Woche  → ~86,7 h/Monat
    MINIJOB = "MINIJOB"           # ~10 h/Woche     → ~43,3 h/Monat

    @property
    def weekly_hours(self) -> float:
        return {
            "FULLTIME_40": 40.0,
            "MIN_24": 24.0,
            "MAX_20": 20.0,
            "MINIJOB": 10.0,
        }[self.value]

    @property
    def monthly_target_hours(self) -> float:
        """Durchschnittliche Sollstunden pro Monat (Wochen × 52/12)."""
        return round(self.weekly_hours * 52 / 12, 2)


class RuleType(str, Enum):
    BLOCKED = "BLOCKED"       # darf diese Schicht/Tag nicht arbeiten
    PREFERRED = "PREFERRED"   # bevorzugt diese Schicht/Tag
    AVOID = "AVOID"           # meidet diese Schicht/Tag (weiche Regel)
    VACATION = "VACATION"     # Urlaub (zählt als gearbeitet im Stundenkonto)
    SICK = "SICK"             # Krank (zählt nicht als gearbeitet)


class RuleScope(str, Enum):
    SHIFT_TYPE = "SHIFT_TYPE"         # gilt für einen bestimmten Schichttyp
    DAY_OF_WEEK = "DAY_OF_WEEK"       # gilt für einen Wochentag
    SPECIFIC_DATE = "SPECIFIC_DATE"   # gilt für ein konkretes Datum
    DAY_AND_SHIFT = "DAY_AND_SHIFT"   # kombiniert Wochentag + Schichttyp


class OccupancyLevel(str, Enum):
    LOW = "LOW"       # score < 40  → keine Zwischenschicht nötig
    MEDIUM = "MEDIUM" # score 40–60 → Zwischenschicht bei Skill-Bedarf
    HIGH = "HIGH"     # score > 60  → Zwischenschicht immer Pflicht


class PlanStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"


# Wochentag-Konstanten (0 = Montag, 6 = Sonntag – Python-Konvention)
MONDAY = 0
TUESDAY = 1
WEDNESDAY = 2
THURSDAY = 3
FRIDAY = 4
SATURDAY = 5
SUNDAY = 6
