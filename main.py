"""
Einstiegspunkt: startet die Schichtplanungs-Desktop-App.
"""
import sys
from datetime import date
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.database.connection import init_db, get_session
from src.services.employee_service import EmployeeService, seed_employees
from src.ui.main_window import MainWindow
from src.ui.styles import APP_STYLESHEET

_ICON_PATH = Path(__file__).parent / "assets" / "icon.png"


def bootstrap() -> None:
    """Initialisiert Datenbank und seeded Stammdaten beim ersten Start."""
    init_db()
    with get_session() as session:
        service = EmployeeService(session)
        # Feiertage für aktuelles + nächstes Jahr
        for year in [date.today().year, date.today().year + 1]:
            service.seed_holidays(year)
        # Mitarbeiter (nur beim ersten Start)
        seed_employees(session)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Schichtplanung")
    app.setOrganizationName("Hotel")
    if _ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(_ICON_PATH)))
    app.setStyleSheet(APP_STYLESHEET)

    # DB-Init (blockiert kurz, aber akzeptabel beim Start)
    bootstrap()

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
