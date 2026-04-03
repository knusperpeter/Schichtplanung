# Architektur: Hotel-Schichtplanungstool

## Tech-Stack-Empfehlung

| Komponente | Technologie | Begründung |
|---|---|---|
| Sprache | Python 3.11+ | Ideal für komplexe Algorithmen, riesiges Ökosystem |
| UI | PySide6 (Qt6) | Native Desktop-UI, cross-platform (Win/Mac), professionell |
| Datenbank | SQLite + SQLAlchemy 2.0 | Kein Server nötig, zuverlässig, portable |
| Scheduler | Google OR-Tools (CP-SAT) | Industriestandard für Constraint Satisfaction Problems |
| PDF-Export | ReportLab | Mächtigste Python-PDF-Bibliothek |
| Packaging | PyInstaller | Erstellt .exe / .app ohne Python-Installation |

---

## Schichtdefinitionen (Stammdaten)

```
Frühschicht    (F):  06:00 – 14:30  →  8,5h  →  immer genau 1 Person
Zwischenschicht (Z): 10:15 – 18:45  →  8,5h  →  optional / regelbasiert
Spätschicht    (S):  14:00 – 22:30  →  8,5h  →  mind. 1, ggf. 2 Personen
Nachtschicht   (N):  22:00 – 06:30  →  8,5h  →  immer genau 1 Person
```

---

## Mitarbeiter-Datenmodell

```
Employee
├── id, name
├── skill_level: EXPERT | MEDIUM | BEGINNER
├── contract_type: FULLTIME_40 | MIN_24 | MAX_20 | MINIJOB_10
├── target_hours_per_month: float          # aus Vertragstyp abgeleitet
├── prefers_between_shift: bool            # Jasmin = True
└── max_late_shifts_per_week: int | None   # Simon = 2, sonst None
```

**Mitarbeitertabelle:**

| Name | Skill | Vertrag | Std/Woche | Präferenz | Einschränkungen |
|---|---|---|---|---|---|
| Allen | EXPERT | FULLTIME | 40h | Nacht | kein Früh, kein Zwischen |
| Simon | EXPERT | FULLTIME | 40h | Nacht (stark) | kein Früh, kein Zwischen, max 2× Spät/Woche |
| Jasmin | EXPERT | FULLTIME | 40h | Zwischen (stark) | nicht Mittwoch |
| Benze | MEDIUM | FULLTIME | 40h | kein Sonntag | kein Nacht, kein Früh-So |
| Ilgar | BEGINNER | FULLTIME | 40h | – | kein Nacht, Spät nur mit 2. Person |
| Pia | EXPERT | MIN_24 | ≥24h | – | nur Früh |
| Dimitri | BEGINNER | MAX_20 | ≤20h | – | kein Nacht, kein Mo/Di/Mi, nur Früh+Zwischen |
| Lena | MEDIUM | MINIJOB | ~10h | – | kein Nacht, nur Wochenende, nur Früh+Zwischen |

---

## Datenbankschema (SQLite)

```sql
-- Mitarbeiter
Employee (id, name, skill_level, contract_type, target_hours_per_month,
          prefers_between_shift, max_late_shifts_per_week)

-- Verfügbarkeitsregeln pro Mitarbeiter
AvailabilityRule (id, employee_id,
                  rule_type: BLOCKED | PREFERRED | AVOID,
                  scope: SHIFT_TYPE | DAY_OF_WEEK | SPECIFIC_DATE,
                  shift_type: F|Z|S|N | NULL,
                  day_of_week: 0-6 | NULL,
                  specific_date: date | NULL)

-- Hotelbelegung (Input)
DailyOccupancy (date PRIMARY KEY,
                checkins int,
                checkouts int,
                occupied_rooms int,  -- rollierend berechnet & gespeichert
                occupancy_score float)

-- Planungsperiode
PlanningPeriod (id, start_date, end_date,
                status: DRAFT | PUBLISHED,
                generated_at, published_at)

-- Schichtzuweisung
ShiftAssignment (id, period_id, date, shift_type,
                 employee_id, is_manual_override bool,
                 note text)

-- Monatsstundenkonto (für Übertrag zwischen 2-Wochen-Perioden)
MonthlyHourBalance (id, employee_id, year, month,
                    target_hours, scheduled_hours, delta)
```

---

## Belegungsberechnung

```
Tägliche Belegung = Vortag_belegt + heutige_checkins − heutige_checkouts

Occupancy Score (gewichtet):
  score = 0.5 × checkins + 0.3 × occupied_rooms + 0.2 × checkouts

Stufen:
  LOW:    score <  40  → keine Zwischenschicht nötig
  MEDIUM: score 40–60  → Zwischenschicht bei Skill-Bedarf
  HIGH:   score > 60   → Zwischenschicht immer Pflicht
```

---

## Schichtbedarfs-Regeln (pro Tag)

```
FRÜHSCHICHT (immer 1):
  → Kandidaten: Pia, Jasmin, Benze, Ilgar, Lena (nur WE), Dimitri (nur Do–So)

NACHTSCHICHT (immer 1):
  → Kandidaten: NUR Allen, Simon, Jasmin
  → Jasmin nur wenn keine andere Option

SPÄTSCHICHT (1 oder 2 Personen):
  Person 1:
    EXPERT   → alleine bei jeder Auslastung OK
    MEDIUM   → alleine OK bei LOW/MEDIUM
    BEGINNER → IMMER zweite Person nötig
  Person 2 (falls nötig):
    → Zwischenschicht (Z) überlappend als Unterstützung, ODER
    → zweite Spätschicht (S)

ZWISCHENSCHICHT (optional → Pflicht wenn):
  1. occupied_rooms ≥ 60   (HIGH)
  2. Spät-Person = BEGINNER
  3. Mitarbeiter hat Stundenminus im Monatskonto
  4. Jasmin verfügbar + keine Nacht nötig (Präferenz erfüllen)
  Priorität Besetzung: Jasmin → Dimitri → andere verfügbare
```

---

## Constraint Engine

### Hard Constraints (dürfen nie verletzt werden)

| # | Regel |
|---|---|
| H1 | Verfügbarkeitsregeln (blocked days/shifts) |
| H2 | 11h Ruhezeit zwischen Schichtende und nächstem Schichtbeginn (ArbZG §5) |
| H3 | Max 10h Arbeitszeit pro Tag (ArbZG §3) |
| H4 | Max 48h pro Woche (ArbZG §3) |
| H5 | Simon: max 2 Spätschichten/Woche |
| H6 | Nachtschicht NUR für EXPERT-Mitarbeiter |
| H7 | Beginner Spätschicht → immer 2. Person auf Spät oder Zwischen |
| H8 | Frühschicht/Nachtschicht: genau 1 Person |
| H9 | Keine zwei Schichten am selben Tag für denselben Mitarbeiter |
| H10 | Pia: NUR Frühschicht |
| H11 | Dimitri: MAX 20h/Woche nicht überschreiten |
| H12 | Lena: NUR Wochenende (Sa/So) |
| H13 | Dimitri: nicht Mo/Di/Mi |

### Soft Constraints (Optimierungsziele, gewichtet)

| # | Gewicht | Regel |
|---|---|---|
| S1 | 10 | Jasmin → Zwischenschicht bevorzugen |
| S2 | 9 | Allen/Simon → Nachtschicht bevorzugen |
| S3 | 8 | Stundenkonto-Abweichung minimieren (Monat) |
| S4 | 7 | Benze → kein Sonntag |
| S5 | 6 | Bei Schichtblockwechsel → 2 Tage Pause (erstrebenswert) |
| S6 | 4 | Gleichmäßige Verteilung Wochentage pro Mitarbeiter |
| S7 | 3 | Benze: kein Früh Sonntag |

---

## Scheduling-Algorithmus (OR-Tools CP-SAT)

```python
# Entscheidungsvariablen:
x[e][d][s] ∈ {0,1}  # Mitarbeiter e arbeitet an Tag d in Schicht s

# Harte Constraints als CP-SAT-Constraints codiert
# Weiche Constraints als gewichtete Penalty-Terme in der Zielfunktion

# Zielfunktion (Minimierung):
minimize:
  + Σ penalty_hour_deviation(e)        * 8   # Stundenkonto-Treue
  + Σ penalty_preference_miss(e,d,s)   * Gewicht[S1..S7]
  + Σ penalty_no_2day_gap(e,d)         * 6   # Schichtblockwechsel
```

**Lösungsstrategie:**
1. Harte Constraints einlesen → Domänen reduzieren
2. CP-SAT lösen mit Zeitlimit (z.B. 10 Sekunden)
3. Falls unlösbar → Constraint-Relaxation mit Erklärung (welche Regel verletzt)
4. Lösung als Draft speichern → manuell anpassbar

---

## Schichtblock-Wechsel-Erkennung

```
Schichtblöcke:
  MORNING  = {F, Z}  (Tagbeginn vor 11 Uhr)
  EVENING  = {S}     (Beginn 14 Uhr)
  NIGHT    = {N}     (Beginn 22 Uhr)

Kritische Wechsel (Ruhezeit-Verletzungen):
  N → F:  Nachtende 06:30 + 11h = 17:30 → Frühbeginn 06:00 Folgetag → VERLETZUNG
           → Mindestens 1 Freier Tag nötig (HARD)
  S → N:  Spätende 22:30 → Nachtbeginn 22:00 gleicher Tag → UNMÖGLICH
  N → S:  Nachtende 06:30 + 11h = 17:30 → Spätbeginn 14:00 Folgetag → VERLETZUNG
           → 1 Freier Tag nötig (HARD)
  Alle anderen Wechsel: automatische 11h-Prüfung
```

---

## Monatliches Stundenkonto

```
Monatsziel = target_hours_per_month (aus Stammdaten je Vertragstyp)

Bei Planung:
  scheduled_hours += 8,5h pro Schicht
  delta = scheduled_hours − target_hours_per_month

Steuerung Zwischenschicht:
  IF delta < −8,5h AND Mitarbeiter verfügbar → Zwischenschicht einfügen
  IF delta > +8,5h → keine weiteren Schichten einplanen
```

---

## Systemarchitektur (Schichten)

```
┌──────────────────────────────────────────────────────────────────┐
│  UI-SCHICHT  (PySide6)                                           │
│                                                                  │
│  ┌────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │  PlanView      │  │  EmployeeView    │  │  OccupancyView   │ │
│  │  2-Wochen Grid │  │  CRUD + Regeln   │  │  Eingabe +       │ │
│  │  Drag & Drop   │  │  Verfügbarkeit   │  │  Auslastungsgraf │ │
│  └────────────────┘  └──────────────────┘  └──────────────────┘ │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  ValidationBar  (Echtzeit-Warnungen bei manuellem Edit)  │   │
│  └──────────────────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────────────────┤
│  APPLICATION SERVICES                                            │
│  PlanningService  │  EmployeeService  │  ExportService (PDF)    │
├──────────────────────────────────────────────────────────────────┤
│  DOMAIN LAYER                                                    │
│  OccupancyCalculator  │  ShiftRequirementEngine                  │
│  ConstraintBuilder    │  CPSATScheduler                          │
│  LaborLawValidator    │  HourBalanceTracker                      │
├──────────────────────────────────────────────────────────────────┤
│  DATA ACCESS LAYER                                               │
│  EmployeeRepository  │  OccupancyRepository  │  PlanRepository  │
│  SQLAlchemy ORM                                                   │
├──────────────────────────────────────────────────────────────────┤
│  SQLite Datenbank  (eine .db-Datei, lokal)                       │
└──────────────────────────────────────────────────────────────────┘
```

---

## UI: 2-Wochen-Planungsansicht

```
       Mo   Di   Mi   Do   Fr   Sa   So  |  Mo   Di   Mi   ...
Allen   N    N    -    N    N    -    -   |   N    N    -   ...
Simon   N    -    N    -    N    -    -   |   -    N    -   ...
Jasmin  Z    Z   [X]   Z    F    Z    Z   |   Z    Z   [X]  ...
Benze   F    S    F    F    S    -   [!]  |   F    F    S   ...
Ilgar   F    S²   F    -    S²   F    -   |   F    -    S²  ...
Pia     F    F    F    -    F    F    -   |   F    F    F   ...
Dimitri -    -    -    Z    Z    F    F   |   -    -    -   ...
Lena    -    -    -    -    -    F    Z   |   -    -    -   ...

Legende:
  F  = Frühschicht        Z  = Zwischenschicht
  S  = Spätschicht        N  = Nachtschicht
  S² = Spät (2 Personen)
  [X] = gesperrt (Verfügbarkeitsregel)
  [!] = Warnung (z.B. Präferenz verletzt)
  Farben: Früh=blau, Zwischen=grün, Spät=orange, Nacht=dunkelblau
```

---

## PDF-Export (Struktur)

```
Seite 1: Übersicht 2-Wochen-Plan (Tabelle: Tage × Mitarbeiter)
Seite 2: Einzelansicht pro Mitarbeiter (Schichten + Stundensumme)
Seite 3: Auslastungsübersicht + Stundenkontensalden
Footer:  Generiert am [Datum] | Status: Draft / Veröffentlicht
```

---

## Implementierungs-Reihenfolge

### Phase 1 – Datenbasis
- SQLite-Schema + SQLAlchemy-Modelle
- Mitarbeiter-CRUD mit Verfügbarkeitsregeln
- Belegungseingabe + rollierende Berechnung

### Phase 2 – Kernlogik
- ShiftRequirementEngine (Tagesbedarf ermitteln)
- ConstraintBuilder → CP-SAT-Modell aufbauen
- CPSATScheduler (Plan generieren)
- LaborLawValidator (11h, max 10h/Tag, max 48h/Woche)
- HourBalanceTracker (Monatskonto)

### Phase 3 – UI
- 2-Wochen-Grid mit Farbkodierung
- Manuelle Anpassung + Echtzeit-Validierung
- Drag & Drop (optional)

### Phase 4 – Export & Feinschliff
- PDF-Export (ReportLab)
- Constraint-Relaxation mit Erklärungen bei unlösbaren Plänen
- PyInstaller-Packaging (.exe / .app)

---

## Offene Punkte – Ausgearbeitet

---

### 1. Feiertage (Bayern)

**Bundesland:** Bayern – bayerische Feiertage werden automatisch aus einer statischen Liste geladen (inkl. regionaler Feiertage wie Mariä Himmelfahrt).

**Verhalten:**
- Feiertage erscheinen im Plan farblich markiert
- Arbeit an Feiertagen ist möglich und wird automatisch als **Überstunden** ins Stundenkonto gebucht
- Die geplanten Stunden zählen regulär UND werden zusätzlich als Feiertagszuschlag vermerkt

**Datenbankergänzung:**
```sql
PublicHoliday (date PRIMARY KEY, name text, is_regional bool)
-- wird einmalig befüllt, jährlich aktualisierbar
```

**Bayerische Feiertage (Auswahl):**
Neujahr, Heilige Drei Könige, Karfreitag, Ostermontag, Tag der Arbeit,
Christi Himmelfahrt, Pfingstmontag, Fronleichnam, Mariä Himmelfahrt*,
Tag der Deutschen Einheit, Allerheiligen, 1./2. Weihnachtstag
(*nur in Gemeinden mit überwiegend kath. Bevölkerung)

---

### 2. Urlaubsverwaltung

Da keine direkte HR-System-Anbindung möglich ist, gibt es drei Optionen:

#### Option A – Manuelle Eingabe im Tool (empfohlen)
- Schichtleiter trägt Urlaubstage pro Mitarbeiter direkt im Tool ein
- Urlaubstage werden als `BLOCKED`-Regel mit Typ `VACATION` gespeichert
- Jahresurlaubskontingent (Standard: 24 Tage bei 40h/Woche nach BUrlG) wird pro Mitarbeiter hinterlegt
- Tool zeigt verbleibende Urlaubstage an

```sql
-- Erweiterung AvailabilityRule:
rule_type: BLOCKED | PREFERRED | AVOID | VACATION | SICK

-- Jahresurlaubskonto:
VacationBalance (id, employee_id, year,
                 entitlement_days int,   -- z.B. 24
                 used_days int,
                 remaining_days int)
```

#### Option B – CSV-Import
- HR-System exportiert Urlaubsdaten als CSV
- Tool bietet Import-Dialog: Datei auswählen → Vorschau → Bestätigen
- Format: `mitarbeiter_name, datum_von, datum_bis, typ (Urlaub/Krank)`
- Vorteil: kein manueller Aufwand nach einmaliger Einrichtung

#### Option C – Hybrid
- Urlaubskontingent einmalig manuell hinterlegen
- Einzelne Urlaubstage per CSV-Import oder manuell nachtragen
- **Empfehlung:** Option C – robusteste Lösung ohne IT-Abhängigkeit

**Urlaub im Stundenkonto:**
- Urlaubstage zählen als gearbeitete Stunden (Urlaubsentgelt nach BUrlG)
- Berechnung: `Urlaubstag = Durchschnittliche tägliche Arbeitszeit des Mitarbeiters`

---

### 3. Stundenkonto & Überstunden

**Regeln:**
- Überstunden werden **monatsübergreifend übertragen** (kein Reset)
- **Ziel:** Stundenausgleich bis Jahresende (erstrebenswert, keine Pflicht)
- **Keine Obergrenze** für Überstunden-Akkumulation
- Jahresübertrag ins Folgejahr ist erlaubt

**Datenbankmodell:**
```sql
HourBalance (id, employee_id, year, month,
             target_hours float,        -- Sollstunden des Monats
             scheduled_hours float,     -- geplante Schichtstunden
             holiday_bonus_hours float, -- Feiertagszuschläge
             vacation_hours float,      -- Urlaubsstunden (zählen als gearbeitet)
             balance_delta float,       -- Differenz: scheduled − target
             cumulative_balance float)  -- laufendes Gesamtkonto
```

**Jahresend-Warnung:**
- Ab Oktober: Tool zeigt Hinweis wenn `cumulative_balance > 0` (Überstunden vorhanden)
- Vorschlag: Zwischenschichten reduzieren / freie Tage einplanen zum Abbau

**Überstundenschwelle:**
- Alles über dem Monatssoll gilt als Überstunden
- Keine automatische Auszahlung – rein informativ im Tool

---

### 4. Backup & Restore

**Manuelles Backup:**
- Menüpunkt „Datenbank sichern" → Dateiauswahl-Dialog → .db-Kopie speichern
- Dateiname enthält automatisch Zeitstempel: `schichtplan_backup_2025-04-01.db`

**Automatisches Backup:**
- Konfigurierbar: täglich / wöchentlich beim Programmstart oder -ende
- Zielordner einstellbar (lokaler Pfad, Netzlaufwerk, OneDrive/Dropbox-Ordner)
- Aufbewahrung: letzten N Backups behalten (Standard: 10), ältere werden gelöscht

**Restore:**
- Menüpunkt „Datenbank wiederherstellen" → .db-Datei auswählen → Bestätigung → Neustart

**Konfiguration (settings.json):**
```json
{
  "backup": {
    "auto_backup": true,
    "trigger": "on_close",
    "target_dir": "C:/Users/.../Backups/Schichtplan",
    "keep_last_n": 10
  }
}
```
