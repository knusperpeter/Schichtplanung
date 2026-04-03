"""
Arbeitsrechtliche Validierung nach deutschem Recht (ArbZG).

Relevante Paragrafen:
  §3  Max. 8h/Tag, erweiterbar auf 10h bei Ausgleich über 6 Monate
  §5  Mind. 11h ununterbrochene Ruhezeit zwischen Arbeitsende und -beginn
  §6  Nachtarbeitnehmer: max. 8h/Nacht im Durchschnitt

Schichtzeiten (alle Dauern 8,5h):
  Frühschicht   (F): 06:00 – 14:30
  Zwischenschicht (Z): 10:15 – 18:45
  Spätschicht   (S): 14:00 – 22:30
  Nachtschicht  (N): 22:00 – 06:30 (endet am Folgetag)
"""
from dataclasses import dataclass
from datetime import date

from src.domain.enums import ShiftType

# Schichtzeiten in Minuten ab Mitternacht
# Nachtschicht endet formal um 06:30 des Folgetags → 6*60+30 + 1440 = 1830
SHIFT_START_MIN: dict[ShiftType, int] = {
    ShiftType.EARLY:  6 * 60,           # 360
    ShiftType.MIDDLE: 10 * 60 + 15,     # 615
    ShiftType.LATE:   14 * 60,          # 840
    ShiftType.NIGHT:  22 * 60,          # 1320
}

SHIFT_END_MIN: dict[ShiftType, int] = {
    ShiftType.EARLY:  14 * 60 + 30,     # 870
    ShiftType.MIDDLE: 18 * 60 + 45,     # 1125
    ShiftType.LATE:   22 * 60 + 30,     # 1350
    ShiftType.NIGHT:  6 * 60 + 30 + 1440,  # 1830 (Folgetag)
}

REST_REQUIRED_MINUTES = 11 * 60  # ArbZG §5: 11 Stunden = 660 Minuten


def rest_minutes(s1: ShiftType, s2: ShiftType, day_gap: int = 1) -> int:
    """
    Berechnet die Ruhezeit in Minuten zwischen Ende von s1 an Tag d
    und Beginn von s2 an Tag d + day_gap.

    Args:
        s1:       Schicht des ersten Tages.
        s2:       Schicht des zweiten Tages (day_gap Tage später).
        day_gap:  Abstand in Tagen (1 = direkt aufeinanderfolgend).
    """
    return SHIFT_START_MIN[s2] + day_gap * 1440 - SHIFT_END_MIN[s1]


def is_rest_violation(s1: ShiftType, s2: ShiftType, day_gap: int = 1) -> bool:
    """True wenn die Ruhezeit zwischen s1 (Tag d) und s2 (Tag d+day_gap) < 11h."""
    return rest_minutes(s1, s2, day_gap) < REST_REQUIRED_MINUTES


# Vorberechnete verbotene Folgeschichten bei gap=1 (direkt aufeinanderfolgend)
# Ruhezeiten (in Minuten):
#   S → F:  360+1440−1350 =  450  < 660  VIOLATION
#   N → F:  360+1440−1830 =  −30  < 660  VIOLATION (unmöglich)
#   N → Z:  615+1440−1830 =  225  < 660  VIOLATION
#   N → S:  840+1440−1830 =  450  < 660  VIOLATION
FORBIDDEN_NEXT_DAY: frozenset[tuple[ShiftType, ShiftType]] = frozenset({
    (ShiftType.LATE,  ShiftType.EARLY),   # 7,5h Pause
    (ShiftType.NIGHT, ShiftType.EARLY),   # unmöglich (−0,5h)
    (ShiftType.NIGHT, ShiftType.MIDDLE),  # 3,75h Pause
    (ShiftType.NIGHT, ShiftType.LATE),    # 7,5h Pause
})


@dataclass
class ScheduleViolation:
    employee_name: str
    date1: date
    shift1: ShiftType
    date2: date
    shift2: ShiftType
    actual_rest_minutes: int
    message: str


def validate_employee_schedule(
    employee_name: str,
    assignments: list[tuple[date, ShiftType]],  # sortiert nach Datum
) -> list[ScheduleViolation]:
    """
    Prüft die Schichtenfolge eines Mitarbeiters auf ArbZG-Verstöße.

    Args:
        employee_name: Name des Mitarbeiters (für Fehlermeldungen).
        assignments:   Liste (datum, schichttyp) aufsteigend sortiert.

    Returns:
        Liste aller Verstöße (leer = kein Verstoß).
    """
    violations: list[ScheduleViolation] = []
    sorted_assignments = sorted(assignments, key=lambda x: x[0])

    for i in range(len(sorted_assignments) - 1):
        d1, s1 = sorted_assignments[i]
        d2, s2 = sorted_assignments[i + 1]
        day_gap = (d2 - d1).days
        if day_gap <= 0:
            continue  # gleicher Tag – wird durch max-1-shift-per-day abgedeckt
        if day_gap > 2:
            continue  # genug Abstand, keine Prüfung nötig

        rest = rest_minutes(s1, s2, day_gap)
        if rest < REST_REQUIRED_MINUTES:
            violations.append(ScheduleViolation(
                employee_name=employee_name,
                date1=d1,
                shift1=s1,
                date2=d2,
                shift2=s2,
                actual_rest_minutes=rest,
                message=(
                    f"{employee_name}: {s1.label} am {d1} endet {_fmt_time(SHIFT_END_MIN[s1])}, "
                    f"{s2.label} am {d2} beginnt {_fmt_time(SHIFT_START_MIN[s2])} → "
                    f"nur {rest // 60}h {rest % 60}min Pause (mind. 11h)"
                ),
            ))

    return violations


def validate_weekly_hours(
    employee_name: str,
    assignments: list[tuple[date, ShiftType]],
    hours_per_shift: float = 8.5,
    max_weekly_hours: float = 48.0,
) -> list[str]:
    """
    Prüft ob wöchentliche Arbeitsstunden 48h überschreiten (ArbZG §3).
    Gibt eine Liste von Warnungstexten zurück.
    """
    from collections import defaultdict
    week_hours: dict[int, float] = defaultdict(float)

    for d, _ in assignments:
        # ISO-Kalenderwoche
        week_num = d.isocalendar().week
        week_year = d.isocalendar().year
        key = week_year * 100 + week_num
        week_hours[key] += hours_per_shift

    warnings = []
    for key, hours in week_hours.items():
        if hours > max_weekly_hours:
            year, week = divmod(key, 100)
            warnings.append(
                f"{employee_name}: KW {week}/{year} – {hours:.1f}h > 48h (ArbZG §3)"
            )
    return warnings


def _fmt_time(minutes: int) -> str:
    """Formatiert Minuten-ab-Mitternacht als HH:MM."""
    minutes = minutes % 1440
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
