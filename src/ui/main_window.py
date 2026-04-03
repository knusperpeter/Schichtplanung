"""
MainWindow – Hauptfenster der Anwendung.

Struktur:
  ┌────────────────────────────────────────────────────────┐
  │  Menüleiste  (Datei · Bearbeiten · Hilfe)              │
  ├────────────────────────────────────────────────────────┤
  │  Tabs: [Plan] [Belegung] [Mitarbeiter]                 │
  │  ┌──────────────────────────────────────────────────┐  │
  │  │  (Tab-Inhalt)                                    │  │
  │  └──────────────────────────────────────────────────┘  │
  ├────────────────────────────────────────────────────────┤
  │  ValidationBar  (ArbZG-Verstöße / Warnungen)           │
  └────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QMenuBar, QMenu, QMessageBox, QFileDialog, QStatusBar,
)

from src.ui.views.plan_view import PlanView
from src.ui.views.occupancy_view import OccupancyView
from src.ui.views.employee_view import EmployeeView
from src.ui.widgets.validation_bar import ValidationBar


class MainWindow(QMainWindow):
    """Haupt-App-Fenster."""

    APP_TITLE = "Schichtplanung – Hotel"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(self.APP_TITLE)
        self.resize(1280, 780)
        self.setMinimumSize(900, 600)
        self._setup_ui()
        self._setup_menu()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)

        # Tab 1: Plan
        self._plan_view = PlanView()
        self._tabs.addTab(self._plan_view, "📋  Plan")

        # Tab 2: Belegung
        self._occ_view = OccupancyView()
        self._tabs.addTab(self._occ_view, "🏨  Belegung")

        # Tab 3: Mitarbeiter
        self._emp_view = EmployeeView()
        self._tabs.addTab(self._emp_view, "👥  Mitarbeiter")

        root.addWidget(self._tabs, 1)

        # ValidationBar (untere Statusleiste)
        self._val_bar = ValidationBar()
        root.addWidget(self._val_bar)

        # Verbindungen
        self._plan_view.violations_changed.connect(self._on_violations_changed)
        self._occ_view.occupancy_saved.connect(self._on_occupancy_saved)

    def _setup_menu(self) -> None:
        menu_bar = self.menuBar()

        # Datei
        file_menu = menu_bar.addMenu("Datei")

        export_action = file_menu.addAction("📄  Als PDF exportieren…")
        export_action.triggered.connect(self._export_pdf)
        export_action.setShortcut("Ctrl+P")

        file_menu.addSeparator()

        backup_action = file_menu.addAction("💾  Datenbank sichern…")
        backup_action.triggered.connect(self._backup_db)

        restore_action = file_menu.addAction("📂  Backup wiederherstellen…")
        restore_action.triggered.connect(self._restore_db)

        file_menu.addSeparator()

        quit_action = file_menu.addAction("Beenden")
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)

        # Ansicht
        view_menu = menu_bar.addMenu("Ansicht")
        plan_action = view_menu.addAction("Plan")
        plan_action.triggered.connect(lambda: self._tabs.setCurrentIndex(0))
        occ_action = view_menu.addAction("Belegung")
        occ_action.triggered.connect(lambda: self._tabs.setCurrentIndex(1))
        emp_action = view_menu.addAction("Mitarbeiter")
        emp_action.triggered.connect(lambda: self._tabs.setCurrentIndex(2))

        # Hilfe
        help_menu = menu_bar.addMenu("Hilfe")
        about_action = help_menu.addAction("Über…")
        about_action.triggered.connect(self._show_about)

    # ------------------------------------------------------------------
    # Slot-Handler
    # ------------------------------------------------------------------

    def _on_violations_changed(self, violations: list[str], warnings: list[str]) -> None:
        self._val_bar.show_violations(violations, warnings)

    def _on_occupancy_saved(self) -> None:
        # Statusmeldung in Validierungsleiste
        self._val_bar.show_ok()

    # ------------------------------------------------------------------
    # Menü-Aktionen
    # ------------------------------------------------------------------

    def _export_pdf(self) -> None:
        from src.services.export_service import ExportService
        path, _ = QFileDialog.getSaveFileName(
            self, "Plan als PDF speichern", f"schichtplan_{date.today()}.pdf",
            "PDF-Dateien (*.pdf)"
        )
        if not path:
            return
        try:
            period_id = self._plan_view._current_period_id
            if not period_id:
                QMessageBox.warning(self, "Kein Plan", "Bitte zuerst einen Plan generieren.")
                return
            ExportService().export_plan_pdf(period_id, path)
            QMessageBox.information(self, "Export erfolgreich", f"Plan gespeichert unter:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export-Fehler", str(exc))

    def _backup_db(self) -> None:
        import shutil
        from pathlib import Path
        from src.database.connection import DEFAULT_DB_PATH
        today_str = date.today().strftime("%Y-%m-%d")
        default_name = f"schichtplan_backup_{today_str}.db"
        path, _ = QFileDialog.getSaveFileName(
            self, "Datenbank sichern", default_name, "SQLite-Datenbank (*.db)"
        )
        if not path:
            return
        try:
            shutil.copy2(DEFAULT_DB_PATH, path)
            QMessageBox.information(self, "Backup erstellt", f"Backup gespeichert:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Backup-Fehler", str(exc))

    def _restore_db(self) -> None:
        import shutil
        from src.database.connection import DEFAULT_DB_PATH
        path, _ = QFileDialog.getOpenFileName(
            self, "Backup auswählen", "", "SQLite-Datenbank (*.db)"
        )
        if not path:
            return
        confirm = QMessageBox.question(
            self, "Backup wiederherstellen",
            "Die aktuelle Datenbank wird überschrieben!\n\nFortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            shutil.copy2(path, DEFAULT_DB_PATH)
            QMessageBox.information(
                self, "Wiederhergestellt",
                "Backup wurde eingespielt.\nBitte Anwendung neu starten."
            )
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", str(exc))

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            f"Über {self.APP_TITLE}",
            "<b>Schichtplanungstool – Hotel</b><br><br>"
            "Automatische 2-Wochen-Schichtplanung mit CP-SAT Solver.<br><br>"
            "Phasen:<br>"
            "✓ Phase 1: Datenbasis<br>"
            "✓ Phase 2: Scheduling-Logik<br>"
            "✓ Phase 3: Desktop-UI<br>"
            "✓ Phase 4: PDF-Export<br>",
        )
