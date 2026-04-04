# Schichtplanung – Hotel

Automatische 2-Wochen-Schichtplanung für Hotelbetriebe. Der integrierte CP-SAT-Solver erstellt arbeitsrechtlich konforme Pläne auf Basis von Belegungsdaten und Mitarbeiterverfügbarkeiten.

![Windows Build](https://github.com/knusperpeter/Schichtplanung/actions/workflows/build-windows.yml/badge.svg)
![macOS Build](https://github.com/knusperpeter/Schichtplanung/actions/workflows/build-macos.yml/badge.svg)

---

## Features

- **Automatische Planerstellung** – CP-SAT-Solver (Google OR-Tools) generiert optimale 2-Wochen-Pläne
- **Belegungsbasierte Planung** – Schichtbedarf wird anhand von Check-in/Check-out-Daten berechnet
- **Manuelle Anpassungen** – Einzelne Schichten per Klick überschreiben
- **Arbeitsrechtliche Validierung** – Prüft Ruhezeiten, Wochenstunden und Nachtschichtlimits (ArbZG)
- **Mitarbeiterverwaltung** – Profile, Verfügbarkeitsregeln, Urlaubsplanung
- **PDF-Export** – Fertige Pläne als PDF ausgeben
- **Dark Mode** – Umschaltbar, wird beim nächsten Start wiederhergestellt
- **Datenbank-Backup** – Sichern und Wiederherstellen per Menü

---

## Screenshots

| Plan | Belegung | Mitarbeiter |
|------|----------|-------------|
| Schichtplan-Grid mit Auslastungsbalken | Check-in/Check-out Eingabe | Profil- und Regelverwaltung |

---

## Installation

### Windows

1. [Actions → Windows Build](../../actions/workflows/build-windows.yml) → aktuellsten erfolgreichen Run öffnen
2. Unter **Artifacts** → `Schichtplanung_Setup.exe` herunterladen
3. Installer ausführen – kein Python erforderlich

### macOS

1. [Actions → macOS Build](../../actions/workflows/build-macos.yml) → aktuellsten erfolgreichen Run öffnen
2. Unter **Artifacts** → `Schichtplanung_macOS` herunterladen → `Schichtplanung.dmg` entpacken
3. DMG öffnen → App in den Ordner **Programme** ziehen

> **Erster Start:** Da die App nicht mit einem Apple-Entwicklerzertifikat signiert ist,
> erscheint beim Doppelklick eine Sicherheitswarnung.
> **Lösung:** Rechtsklick auf die App → **Öffnen** → im Dialog erneut **Öffnen** klicken.
> Danach startet die App beim nächsten Doppelklick normal.

---

## Entwicklung

### Voraussetzungen

- Python 3.12+
- Abhängigkeiten installieren:

```bash
pip install -r requirements.txt
```

### Starten

```bash
python main.py
```

### Windows-Installer bauen

Auf einem Windows-Rechner:

```bat
build.bat
```

Erzeugt `installer_output/Schichtplanung_Setup.exe`.

Der Build läuft außerdem automatisch über GitHub Actions bei jedem Push auf `main`.

---

## Projektstruktur

```
├── main.py                   Einstiegspunkt
├── assets/                   Icons (SVG, PNG, ICNS, ICO)
├── src/
│   ├── database/             SQLAlchemy-Modelle & Verbindung
│   ├── domain/               Scheduler, Validator, Berechnungen
│   ├── repositories/         Datenbankzugriff
│   ├── services/             Export, Mitarbeiter-Service
│   └── ui/
│       ├── views/            Plan-, Belegungs-, Mitarbeiter-View
│       ├── widgets/          ShiftButton, ValidationBar
│       ├── dialogs/          Generierungs-Dialog
│       └── styles.py         shadcn/ui Zinc Design-System
├── build.bat                 Windows Build-Skript
├── installer.iss             Inno Setup Konfiguration
└── Schichtplanung.spec       PyInstaller Spec
```

---

## Schichttypen

| Kürzel | Schicht | Zeit |
|--------|---------|------|
| F | Frühschicht | 06:00 – 14:30 |
| Z | Zwischenschicht | 10:15 – 18:45 |
| S | Spätschicht | 14:00 – 22:30 |
| N | Nachtschicht | 22:00 – 06:30 |

---

## Technologie

- **UI** – PySide6 (Qt 6), Design nach [shadcn/ui](https://ui.shadcn.com) Zinc-Palette
- **Solver** – Google OR-Tools CP-SAT
- **Datenbank** – SQLite via SQLAlchemy
- **PDF** – ReportLab
- **Installer** – PyInstaller + Inno Setup
