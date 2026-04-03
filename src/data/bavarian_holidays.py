"""
Bayerische Feiertage.

Feste Feiertage werden statisch definiert.
Bewegliche Feiertage (osterabhängig) werden per Algorithmus berechnet.
"""
from datetime import date, timedelta


def _easter(year: int) -> date:
    """Berechnet das Osterdatum nach dem Algorithmus von Butcher/Meeus."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def get_bavarian_holidays(year: int) -> list[tuple[date, str, bool]]:
    """
    Gibt alle bayerischen Feiertage für das angegebene Jahr zurück.

    Returns:
        Liste von (datum, name, is_regional)
        is_regional=True → nur in Gemeinden mit überwiegend kath. Bevölkerung
    """
    easter = _easter(year)

    holidays: list[tuple[date, str, bool]] = [
        # Feste gesetzliche Feiertage
        (date(year, 1, 1),  "Neujahr",                          False),
        (date(year, 1, 6),  "Heilige Drei Könige",              False),
        (date(year, 5, 1),  "Tag der Arbeit",                   False),
        (date(year, 10, 3), "Tag der Deutschen Einheit",        False),
        (date(year, 11, 1), "Allerheiligen",                    False),
        (date(year, 12, 25),"1. Weihnachtstag",                 False),
        (date(year, 12, 26),"2. Weihnachtstag",                 False),
        # Bewegliche Feiertage (osterabhängig)
        (easter - timedelta(days=2),  "Karfreitag",             False),
        (easter + timedelta(days=1),  "Ostermontag",            False),
        (easter + timedelta(days=39), "Christi Himmelfahrt",    False),
        (easter + timedelta(days=50), "Pfingstmontag",          False),
        (easter + timedelta(days=60), "Fronleichnam",           False),
        # Regionaler Feiertag
        (date(year, 8, 15), "Mariä Himmelfahrt",                True),
    ]
    return sorted(holidays, key=lambda x: x[0])


def get_holiday_dates(year: int, include_regional: bool = True) -> set[date]:
    """Gibt alle Feiertagsdaten als Set zurück."""
    return {
        d for d, _, regional in get_bavarian_holidays(year)
        if include_regional or not regional
    }
