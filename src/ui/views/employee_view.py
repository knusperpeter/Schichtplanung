"""
EmployeeView – Übersicht aller Mitarbeiter mit Verfügbarkeitsregeln.

Layout:
  ┌─────────────────────────┬──────────────────────────────────────┐
  │  Mitarbeiterliste       │  Stammdaten (Info-Box)               │
  │  ──────────────────     │  ────────────────────────────────    │
  │  Allen  [EXPERT]        │  Verfügbarkeitsregeln  [Bearbeiten]  │
  │  Benze  [MEDIUM]        │  Tabelle (+ Löschen-Buttons)         │
  │  ...                    │  [Neue Regel Form – nur Edit-Modus]  │
  └─────────────────────────┴──────────────────────────────────────┘
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QTableWidget, QTableWidgetItem, QFrame,
    QHeaderView, QFormLayout, QSplitter, QPushButton, QComboBox,
    QLineEdit, QDateEdit, QMessageBox, QSizePolicy, QDialog,
    QDialogButtonBox, QSpinBox, QDoubleSpinBox, QCheckBox,
)

from src.database.connection import get_session
from src.database.models import AvailabilityRule, Employee
from src.domain.enums import RuleType, RuleScope, ShiftType, SkillLevel, ContractType
from src.repositories.employee_repository import EmployeeRepository
from src.ui.styles import SKILL_COLOR, SKILL_LABEL, CONTRACT_LABEL

# ---------------------------------------------------------------------------
# Konstanten / Übersetzungen
# ---------------------------------------------------------------------------

RULE_TYPE_DE = {
    "BLOCKED":   "Gesperrt",
    "PREFERRED": "Bevorzugt",
    "AVOID":     "Vermeiden",
    "VACATION":  "Urlaub",
    "SICK":      "Krank",
}
RULE_TYPE_COLOR = {
    "BLOCKED":   "#991B1B",   # auf weiß: 10.7:1
    "PREFERRED": "#166534",   # auf weiß: 12.2:1
    "AVOID":     "#92400E",   # auf weiß:  7.1:1
    "VACATION":  "#1A5D9E",   # auf weiß:  6.7:1
    "SICK":      "#6B21A8",   # auf weiß:  8.8:1
}

SCOPE_DE = {
    "SHIFT_TYPE":    "Schichttyp",
    "DAY_OF_WEEK":   "Wochentag",
    "SPECIFIC_DATE": "Datum",
    "DAY_AND_SHIFT": "Tag + Schicht",
}
SHIFT_LABEL_SHORT = {"F": "Früh", "Z": "Zwischen", "S": "Spät", "N": "Nacht"}
SHIFT_ITEMS = [("F", "F – Frühschicht"), ("Z", "Z – Zwischenschicht"),
               ("S", "S – Spätschicht"), ("N", "N – Nachtschicht")]
DAY_NAMES = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
             "Freitag", "Samstag", "Sonntag"]

# Scopes, die eine Schicht-Auswahl brauchen
_SCOPE_NEEDS_SHIFT = {"SHIFT_TYPE", "DAY_AND_SHIFT"}
# Scopes, die eine Wochentag-Auswahl brauchen
_SCOPE_NEEDS_DAY   = {"DAY_OF_WEEK", "DAY_AND_SHIFT"}
# Scopes, die ein Datum brauchen
_SCOPE_NEEDS_DATE  = {"SPECIFIC_DATE"}


class EmployeeView(QWidget):
    """Mitarbeiterübersicht mit editierbaren Verfügbarkeitsregeln."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._employees: list = []
        self._edit_mode = False
        self._setup_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("Mitarbeiter")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        root.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Linke Seite: Mitarbeiterliste ──────────────────────────────
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel("Mitarbeiter"))
        self._list = QListWidget()
        self._list.setMaximumWidth(300)
        self._list.setStyleSheet(
            "QListWidget { border: 1px solid #CBD5E1; border-radius: 4px; }"
            "QListWidget::item { padding: 6px 10px; }"
            "QListWidget::item:selected { background: #2563EB; color: #FFFFFF; }"
        )
        self._list.currentRowChanged.connect(self._on_employee_selected)
        ll.addWidget(self._list)

        new_btn = QPushButton("＋  Neuer Mitarbeiter")
        new_btn.setStyleSheet(
            "background: #2563EB; color: white; font-weight: bold;"
            "border: none; border-radius: 5px; padding: 7px 10px;"
        )
        new_btn.clicked.connect(self._open_new_employee_dialog)
        ll.addWidget(new_btn)

        self._delete_emp_btn = QPushButton("✕  Mitarbeiter löschen")
        self._delete_emp_btn.setStyleSheet(
            "background: #991B1B; color: white; font-weight: bold;"
            "border: none; border-radius: 5px; padding: 7px 10px;"
        )
        self._delete_emp_btn.clicked.connect(self._delete_current_employee)
        ll.addWidget(self._delete_emp_btn)

        splitter.addWidget(left)

        # ── Rechte Seite: Details ──────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(12, 0, 0, 0)
        rl.setSpacing(10)

        # Info-Box
        self._info_frame = QFrame()
        self._info_frame.setStyleSheet(
            "QFrame { border: 1px solid #CBD5E1; border-radius: 6px; padding: 4px; }"
            "QLabel { background: transparent; border: none; }"
        )
        info_layout = QFormLayout(self._info_frame)
        info_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        info_layout.setContentsMargins(12, 10, 12, 10)
        info_layout.setSpacing(6)

        self._name_lbl     = QLabel("–")
        self._skill_lbl    = QLabel("–")
        self._contract_lbl = QLabel("–")
        self._hours_lbl    = QLabel("–")
        self._special_lbl  = QLabel("–")

        for lbl in (self._name_lbl, self._skill_lbl, self._contract_lbl,
                    self._hours_lbl, self._special_lbl):
            lbl.setStyleSheet("font-size: 12px;")

        info_layout.addRow("Name:",          self._name_lbl)
        info_layout.addRow("Skill-Level:",   self._skill_lbl)
        info_layout.addRow("Vertragsart:",   self._contract_lbl)
        info_layout.addRow("Ziel h/Monat:",  self._hours_lbl)
        info_layout.addRow("Besonderheiten:", self._special_lbl)
        rl.addWidget(self._info_frame)

        # Überschrift Regeln + Bearbeiten-Button
        rules_header = QHBoxLayout()
        rules_lbl = QLabel("Verfügbarkeitsregeln")
        rules_lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        rules_header.addWidget(rules_lbl)
        rules_header.addStretch()
        self._edit_btn = QPushButton("✏  Bearbeiten")
        self._edit_btn.setFixedWidth(150)
        self._edit_btn.clicked.connect(self._toggle_edit_mode)
        rules_header.addWidget(self._edit_btn)
        rl.addLayout(rules_header)

        # Regeln-Tabelle (5 Spalten; Spalte 4 = Löschen, nur in Edit-Modus sichtbar)
        self._rules_table = QTableWidget()
        self._rules_table.setColumnCount(5)
        self._rules_table.setHorizontalHeaderLabels(
            ["Typ", "Geltungsbereich", "Details", "Notiz", ""]
        )
        self._rules_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._rules_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Fixed
        )
        self._rules_table.setColumnWidth(4, 100)
        self._rules_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._rules_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._rules_table.verticalHeader().setVisible(False)
        self._rules_table.setStyleSheet("QTableWidget { border: 1px solid #CBD5E1; font-size: 11px; }")
        self._rules_table.setColumnHidden(4, True)
        rl.addWidget(self._rules_table, 1)

        # ── Neue-Regel-Formular (nur in Edit-Modus sichtbar) ──────────
        self._add_form = self._build_add_form()
        self._add_form.setVisible(False)
        rl.addWidget(self._add_form)

        splitter.addWidget(right)
        splitter.setSizes([300, 700])
        root.addWidget(splitter, 1)

    def _build_add_form(self) -> QFrame:
        """Erstellt das Formular zum Hinzufügen einer neuen Regel."""
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { border: 1px solid #CBD5E1; border-radius: 6px; }"
            "QLabel { background: transparent; border: none; }"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        lbl = QLabel("Neue Regel hinzufügen")
        lbl.setStyleSheet("font-weight: bold; color: #2C3E50; font-size: 12px;")
        layout.addWidget(lbl)

        # Zeile 1: Regeltyp + Geltungsbereich
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self._type_combo = QComboBox()
        for key, label in RULE_TYPE_DE.items():
            self._type_combo.addItem(label, key)
        row1.addWidget(QLabel("Typ:"))
        row1.addWidget(self._type_combo, 1)

        row1.addWidget(QLabel("Bereich:"))
        self._scope_combo = QComboBox()
        for key, label in SCOPE_DE.items():
            self._scope_combo.addItem(label, key)
        self._scope_combo.currentIndexChanged.connect(self._on_scope_changed)
        row1.addWidget(self._scope_combo, 1)
        layout.addLayout(row1)

        # Zeile 2: kontextsensitive Felder
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        self._shift_lbl = QLabel("Schicht:")
        self._shift_combo = QComboBox()
        for val, label in SHIFT_ITEMS:
            self._shift_combo.addItem(label, val)
        row2.addWidget(self._shift_lbl)
        row2.addWidget(self._shift_combo, 1)

        self._day_lbl = QLabel("Wochentag:")
        self._day_combo = QComboBox()
        for i, name in enumerate(DAY_NAMES):
            self._day_combo.addItem(name, i)
        row2.addWidget(self._day_lbl)
        row2.addWidget(self._day_combo, 1)

        self._date_lbl = QLabel("Datum:")
        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("dd.MM.yyyy")
        today = date.today()
        self._date_edit.setDate(QDate(today.year, today.month, today.day))
        row2.addWidget(self._date_lbl)
        row2.addWidget(self._date_edit, 1)

        layout.addLayout(row2)

        # Zeile 3: Notiz + Hinzufügen-Button
        row3 = QHBoxLayout()
        row3.setSpacing(8)
        row3.addWidget(QLabel("Notiz:"))
        self._note_edit = QLineEdit()
        self._note_edit.setPlaceholderText("Optional …")
        row3.addWidget(self._note_edit, 1)

        add_btn = QPushButton("＋  Hinzufügen")
        add_btn.setStyleSheet(
            "background: #27AE60; color: white; font-weight: bold;"
            "padding: 5px 14px; border-radius: 4px; border: none;"
        )
        add_btn.clicked.connect(self._add_rule)
        row3.addWidget(add_btn)
        layout.addLayout(row3)

        # Initialen Scope-Zustand setzen
        self._on_scope_changed(0)
        return frame

    # ------------------------------------------------------------------
    # Datenladen / Anzeige
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        with get_session() as session:
            self._employees = EmployeeRepository(session).get_all()

        self._list.clear()
        for emp in self._employees:
            color = SKILL_COLOR.get(emp.skill_level, "#999")
            item = QListWidgetItem(f"  {emp.name}")
            item.setForeground(QBrush(QColor(color)))
            item.setToolTip(
                f"{SKILL_LABEL.get(emp.skill_level, emp.skill_level)} · "
                f"{CONTRACT_LABEL.get(emp.contract_type, emp.contract_type)}"
            )
            self._list.addItem(item)

        if self._employees:
            self._list.setCurrentRow(0)

    def _on_employee_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._employees):
            return
        # Edit-Modus beim Mitarbeiterwechsel beenden
        if self._edit_mode:
            self._set_edit_mode(False)
        self._show_employee(self._employees[row])

    def _show_employee(self, emp) -> None:
        self._name_lbl.setText(f"<b>{emp.name}</b>")

        skill = emp.skill_level
        color = SKILL_COLOR.get(skill, "#999")
        self._skill_lbl.setText(
            f'<span style="color:{color}; font-weight:bold;">'
            f'{SKILL_LABEL.get(skill, skill)}</span>'
        )
        self._contract_lbl.setText(
            CONTRACT_LABEL.get(emp.contract_type, emp.contract_type)
        )
        self._hours_lbl.setText(f"{emp.target_hours_per_month:.1f} h / Monat")

        specials = []
        if emp.prefers_between_shift:
            specials.append("Bevorzugt Zwischenschicht")
        if emp.max_late_shifts_per_week is not None:
            specials.append(f"Max {emp.max_late_shifts_per_week}× Spät/Woche")
        self._special_lbl.setText(", ".join(specials) if specials else "–")

        self._populate_rules_table(emp)

    def _populate_rules_table(self, emp) -> None:
        rules = sorted(emp.availability_rules, key=lambda r: r.rule_type)
        self._rules_table.setRowCount(len(rules))

        for row, rule in enumerate(rules):
            # Typ
            type_item = QTableWidgetItem(RULE_TYPE_DE.get(rule.rule_type, rule.rule_type))
            type_item.setForeground(QBrush(QColor(RULE_TYPE_COLOR.get(rule.rule_type, "#333"))))
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._rules_table.setItem(row, 0, type_item)

            # Geltungsbereich
            scope_item = QTableWidgetItem(SCOPE_DE.get(rule.scope, rule.scope))
            scope_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._rules_table.setItem(row, 1, scope_item)

            # Details
            details = []
            if rule.shift_type:
                details.append(SHIFT_LABEL_SHORT.get(rule.shift_type, rule.shift_type))
            if rule.day_of_week is not None:
                details.append(DAY_NAMES[rule.day_of_week])
            if rule.specific_date:
                details.append(rule.specific_date.strftime("%d.%m.%Y"))
            detail_item = QTableWidgetItem(", ".join(details) if details else "–")
            detail_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._rules_table.setItem(row, 2, detail_item)

            # Notiz
            note_item = QTableWidgetItem(rule.note or "")
            self._rules_table.setItem(row, 3, note_item)

            # Löschen-Button (Spalte 4, nur in Edit-Modus sichtbar)
            del_btn = QPushButton("✕ Entfernen")
            del_btn.setStyleSheet(
                "QPushButton { background: #991B1B; color: white; border: none;"
                " border-radius: 3px; font-size: 10px; padding: 3px 6px; }"
                "QPushButton:hover { background: #7F1111; }"
            )
            rule_id = rule.id
            del_btn.clicked.connect(lambda _checked, rid=rule_id: self._delete_rule(rid))
            self._rules_table.setCellWidget(row, 4, del_btn)

    # ------------------------------------------------------------------
    # Edit-Modus
    # ------------------------------------------------------------------

    def _toggle_edit_mode(self) -> None:
        self._set_edit_mode(not self._edit_mode)

    def _set_edit_mode(self, active: bool) -> None:
        self._edit_mode = active
        self._rules_table.setColumnHidden(4, not active)
        self._add_form.setVisible(active)
        if active:
            self._edit_btn.setText("✓  Fertig")
            self._edit_btn.setStyleSheet(
                "background: #27AE60; color: white; font-weight: bold;"
                "border: none; border-radius: 4px; padding: 5px 10px;"
            )
        else:
            self._edit_btn.setText("✏  Bearbeiten")
            self._edit_btn.setStyleSheet("")

    # ------------------------------------------------------------------
    # Scope-Combo → kontextsensitive Felder ein-/ausblenden
    # ------------------------------------------------------------------

    def _on_scope_changed(self, _index: int) -> None:
        scope = self._scope_combo.currentData()
        needs_shift = scope in _SCOPE_NEEDS_SHIFT
        needs_day   = scope in _SCOPE_NEEDS_DAY
        needs_date  = scope in _SCOPE_NEEDS_DATE

        self._shift_lbl.setVisible(needs_shift)
        self._shift_combo.setVisible(needs_shift)
        self._day_lbl.setVisible(needs_day)
        self._day_combo.setVisible(needs_day)
        self._date_lbl.setVisible(needs_date)
        self._date_edit.setVisible(needs_date)

    # ------------------------------------------------------------------
    # Regel hinzufügen
    # ------------------------------------------------------------------

    def _add_rule(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._employees):
            return
        emp = self._employees[row]

        rule_type = self._type_combo.currentData()
        scope     = self._scope_combo.currentData()
        shift_val = self._shift_combo.currentData() if scope in _SCOPE_NEEDS_SHIFT else None
        day_val   = self._day_combo.currentData()   if scope in _SCOPE_NEEDS_DAY   else None
        date_val: date | None = None
        if scope in _SCOPE_NEEDS_DATE:
            qd = self._date_edit.date()
            date_val = date(qd.year(), qd.month(), qd.day())
        note = self._note_edit.text().strip() or None

        new_rule = AvailabilityRule(
            employee_id=emp.id,
            rule_type=rule_type,
            scope=scope,
            shift_type=shift_val,
            day_of_week=day_val,
            specific_date=date_val,
            note=note,
        )

        try:
            with get_session() as session:
                EmployeeRepository(session).add_rule(new_rule)
        except Exception as exc:
            QMessageBox.warning(self, "Fehler", f"Regel konnte nicht gespeichert werden:\n{exc}")
            return

        self._note_edit.clear()
        self._reload_current_employee()

    # ------------------------------------------------------------------
    # Regel löschen
    # ------------------------------------------------------------------

    def _delete_rule(self, rule_id: int) -> None:
        confirm = QMessageBox.question(
            self, "Regel entfernen",
            "Diese Verfügbarkeitsregel wirklich entfernen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            with get_session() as session:
                repo = EmployeeRepository(session)
                # Lade Regel aus aktiver Session
                from sqlalchemy.orm import Session as _Sess
                rule = session.get(AvailabilityRule, rule_id)
                if rule:
                    repo.delete_rule(rule)
        except Exception as exc:
            QMessageBox.warning(self, "Fehler", f"Regel konnte nicht gelöscht werden:\n{exc}")
            return

        self._reload_current_employee()

    # ------------------------------------------------------------------
    # Hilfsmethode: aktuellen Mitarbeiter frisch aus DB laden & anzeigen
    # ------------------------------------------------------------------

    def _reload_current_employee(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        emp_id = self._employees[row].id
        with get_session() as session:
            self._employees = EmployeeRepository(session).get_all()
        emp = next((e for e in self._employees if e.id == emp_id), None)
        if emp:
            self._show_employee(emp)

    # ------------------------------------------------------------------
    # Neuer Mitarbeiter
    # ------------------------------------------------------------------

    def _delete_current_employee(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._employees):
            return
        emp = self._employees[row]
        confirm = QMessageBox.question(
            self, "Mitarbeiter l\u00f6schen",
            f'Mitarbeiter "{emp.name}" wirklich l\u00f6schen?\n'
            "Alle Verf\u00fcgbarkeitsregeln werden ebenfalls entfernt.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            with get_session() as session:
                repo = EmployeeRepository(session)
                obj = session.get(Employee, emp.id)
                if obj:
                    repo.delete(obj)
        except Exception as exc:
            QMessageBox.warning(self, "Fehler", f"Mitarbeiter konnte nicht gelöscht werden:\n{exc}")
            return

        self.refresh()

    def _open_new_employee_dialog(self) -> None:
        dlg = _NewEmployeeDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_data()
        try:
            with get_session() as session:
                emp = Employee(
                    name=data["name"],
                    skill_level=data["skill_level"],
                    contract_type=data["contract_type"],
                    target_hours_per_month=data["target_hours"],
                    prefers_between_shift=data["prefers_between"],
                    max_late_shifts_per_week=data["max_late"] or None,
                )
                EmployeeRepository(session).create(emp)
                new_id = emp.id
        except Exception as exc:
            QMessageBox.warning(self, "Fehler", f"Mitarbeiter konnte nicht angelegt werden:\n{exc}")
            return

        # Liste neu laden und neuen Mitarbeiter auswählen
        with get_session() as session:
            self._employees = EmployeeRepository(session).get_all()
        self._list.blockSignals(True)
        self._list.clear()
        select_row = 0
        for i, emp in enumerate(self._employees):
            color = SKILL_COLOR.get(emp.skill_level, "#999")
            item = QListWidgetItem(f"  {emp.name}")
            item.setForeground(QBrush(QColor(color)))
            item.setToolTip(
                f"{SKILL_LABEL.get(emp.skill_level, emp.skill_level)} · "
                f"{CONTRACT_LABEL.get(emp.contract_type, emp.contract_type)}"
            )
            self._list.addItem(item)
            if emp.id == new_id:
                select_row = i
        self._list.blockSignals(False)
        self._list.setCurrentRow(select_row)
        self._show_employee(self._employees[select_row])


# ---------------------------------------------------------------------------
# Dialog: Neuer Mitarbeiter
# ---------------------------------------------------------------------------

class _NewEmployeeDialog(QDialog):
    """Formular zum Anlegen eines neuen Mitarbeiters."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Neuer Mitarbeiter")
        self.setMinimumWidth(480)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 16)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)

        # Name
        self._name = QLineEdit()
        self._name.setPlaceholderText("Vor- und Nachname …")
        form.addRow("Name *:", self._name)

        # Skill-Level
        self._skill = QComboBox()
        for key, label in SKILL_LABEL.items():
            self._skill.addItem(label, key)
        form.addRow("Qualifikation *:", self._skill)

        # Vertragstyp
        self._contract = QComboBox()
        for key, label in CONTRACT_LABEL.items():
            self._contract.addItem(label, key)
        self._contract.currentIndexChanged.connect(self._on_contract_changed)
        form.addRow("Vertragstyp *:", self._contract)

        # Soll-Stunden / Monat
        self._hours = QDoubleSpinBox()
        self._hours.setRange(0, 250)
        self._hours.setDecimals(1)
        self._hours.setSuffix(" h")
        form.addRow("Soll h/Monat:", self._hours)

        # Bevorzugt Zwischenschicht
        self._prefers_between = QCheckBox("Bevorzugt Zwischenschicht")
        form.addRow("", self._prefers_between)

        # Max Spätschichten / Woche
        self._max_late = QSpinBox()
        self._max_late.setRange(0, 7)
        self._max_late.setSpecialValueText("–  (kein Limit)")
        form.addRow("Max Spät/Woche:", self._max_late)

        layout.addLayout(form)

        # Buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Anlegen")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        # Startwert für Stunden setzen
        self._on_contract_changed(0)

    def _on_contract_changed(self, _index: int) -> None:
        """Füllt Soll-Stunden automatisch aus dem Vertragstyp."""
        key = self._contract.currentData()
        defaults = {
            "FULLTIME_40": 173.0,
            "MIN_24":      104.0,
            "MAX_20":       86.7,
            "MINIJOB":      43.3,
        }
        self._hours.setValue(defaults.get(key, 0.0))

    def _on_accept(self) -> None:
        if not self._name.text().strip():
            QMessageBox.warning(self, "Pflichtfeld", "Bitte einen Namen eingeben.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "name":           self._name.text().strip(),
            "skill_level":    self._skill.currentData(),
            "contract_type":  self._contract.currentData(),
            "target_hours":   self._hours.value(),
            "prefers_between": self._prefers_between.isChecked(),
            "max_late":       self._max_late.value(),
        }
