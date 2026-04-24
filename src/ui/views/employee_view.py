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
from src.database.models import AvailabilityRule, Employee, OvertimeEntry
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
        self._editing_rule_id: int | None = None
        self._profile_edit_mode = False
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
        title.setObjectName("section-title")
        root.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Linke Seite: Mitarbeiterliste ──────────────────────────────
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel("Mitarbeiter"))
        self._list = QListWidget()
        self._list.setMaximumWidth(300)
        self._list.currentRowChanged.connect(self._on_employee_selected)
        ll.addWidget(self._list)

        new_btn = QPushButton("＋  Neuer Mitarbeiter")
        new_btn.setObjectName("primary")
        new_btn.clicked.connect(self._open_new_employee_dialog)
        ll.addWidget(new_btn)

        self._delete_emp_btn = QPushButton("✕  Mitarbeiter löschen")
        self._delete_emp_btn.setObjectName("destructive")
        self._delete_emp_btn.clicked.connect(self._delete_current_employee)
        ll.addWidget(self._delete_emp_btn)

        splitter.addWidget(left)

        # ── Rechte Seite: Details ──────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(12, 0, 0, 0)
        rl.setSpacing(10)

        # Profil-Header
        profile_header = QHBoxLayout()
        profile_lbl = QLabel("Mitarbeiterprofil")
        profile_lbl.setObjectName("section-title")
        profile_header.addWidget(profile_lbl)
        profile_header.addStretch()
        self._profile_edit_btn = QPushButton("✏  Bearbeiten")
        self._profile_edit_btn.setFixedWidth(150)
        self._profile_edit_btn.clicked.connect(self._toggle_profile_edit)
        profile_header.addWidget(self._profile_edit_btn)
        rl.addLayout(profile_header)

        # Info-Box (Anzeigemodus)
        self._info_frame = QFrame()
        self._info_frame.setObjectName("card")
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
            lbl.setObjectName("info")

        info_layout.addRow("Name:",           self._name_lbl)
        info_layout.addRow("Skill-Level:",    self._skill_lbl)
        info_layout.addRow("Vertragsart:",    self._contract_lbl)
        info_layout.addRow("Ziel h/Monat:",  self._hours_lbl)
        info_layout.addRow("Besonderheiten:", self._special_lbl)
        rl.addWidget(self._info_frame)

        # Info-Box (Bearbeitungsmodus, zunächst versteckt)
        self._info_edit_frame = QFrame()
        self._info_edit_frame.setObjectName("card")
        self._info_edit_frame.setVisible(False)
        edit_outer = QVBoxLayout(self._info_edit_frame)
        edit_outer.setContentsMargins(12, 10, 12, 10)
        edit_outer.setSpacing(8)

        edit_form = QFormLayout()
        edit_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        edit_form.setSpacing(6)

        self._edit_name = QLineEdit()
        edit_form.addRow("Name *:", self._edit_name)

        self._edit_skill = QComboBox()
        for key, label in SKILL_LABEL.items():
            self._edit_skill.addItem(label, key)
        edit_form.addRow("Skill-Level *:", self._edit_skill)

        self._edit_contract = QComboBox()
        for key, label in CONTRACT_LABEL.items():
            self._edit_contract.addItem(label, key)
        edit_form.addRow("Vertragsart *:", self._edit_contract)

        self._edit_hours = QDoubleSpinBox()
        self._edit_hours.setRange(0, 250)
        self._edit_hours.setDecimals(1)
        self._edit_hours.setSuffix(" h")
        edit_form.addRow("Ziel h/Monat:", self._edit_hours)

        self._edit_prefers_between = QCheckBox("Bevorzugt Zwischenschicht")
        edit_form.addRow("", self._edit_prefers_between)

        self._edit_max_late = QSpinBox()
        self._edit_max_late.setRange(0, 7)
        self._edit_max_late.setSpecialValueText("–  (kein Limit)")
        edit_form.addRow("Max Spät/Woche:", self._edit_max_late)

        edit_outer.addLayout(edit_form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_profile_btn = QPushButton("✓  Speichern")
        save_profile_btn.setObjectName("primary")
        save_profile_btn.clicked.connect(self._save_profile)
        btn_row.addWidget(save_profile_btn)
        cancel_profile_btn = QPushButton("Abbrechen")
        cancel_profile_btn.clicked.connect(self._cancel_profile_edit)
        btn_row.addWidget(cancel_profile_btn)
        edit_outer.addLayout(btn_row)

        rl.addWidget(self._info_edit_frame)

        # Überschrift Regeln + Bearbeiten-Button
        rules_header = QHBoxLayout()
        rules_lbl = QLabel("Verfügbarkeitsregeln")
        rules_lbl.setObjectName("section-title")
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
        self._rules_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self._rules_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._rules_table.setColumnWidth(3, 200)
        self._rules_table.setColumnWidth(4, 160)
        self._rules_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._rules_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._rules_table.verticalHeader().setVisible(False)
        self._rules_table.setShowGrid(False)
        self._rules_table.verticalHeader().setDefaultSectionSize(40)
        self._rules_table.verticalHeader().setMinimumSectionSize(40)
        self._rules_table.setColumnHidden(4, True)
        rl.addWidget(self._rules_table, 1)

        # ── Neue-Regel-Formular (nur in Edit-Modus sichtbar) ──────────
        self._add_form = self._build_add_form()
        self._add_form.setVisible(False)
        rl.addWidget(self._add_form)

        # ── Überstundenkonto ───────────────────────────────────────────
        overtime_header = QHBoxLayout()
        overtime_lbl = QLabel("Überstundenkonto")
        overtime_lbl.setObjectName("section-title")
        overtime_header.addWidget(overtime_lbl)
        overtime_header.addStretch()
        self._overtime_total_lbl = QLabel("Gesamt: 0,0 h")
        self._overtime_total_lbl.setObjectName("info")
        overtime_header.addWidget(self._overtime_total_lbl)
        self._add_overtime_btn = QPushButton("＋  Eintrag")
        self._add_overtime_btn.setObjectName("primary")
        self._add_overtime_btn.setFixedWidth(110)
        self._add_overtime_btn.clicked.connect(self._toggle_overtime_form)
        overtime_header.addWidget(self._add_overtime_btn)
        rl.addLayout(overtime_header)

        self._overtime_table = QTableWidget()
        self._overtime_table.setColumnCount(4)
        self._overtime_table.setHorizontalHeaderLabels(["Datum", "Stunden", "Notiz", ""])
        self._overtime_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._overtime_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._overtime_table.setColumnWidth(3, 50)
        self._overtime_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._overtime_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._overtime_table.verticalHeader().setVisible(False)
        self._overtime_table.setShowGrid(False)
        self._overtime_table.verticalHeader().setDefaultSectionSize(36)
        self._overtime_table.verticalHeader().setMinimumSectionSize(36)
        self._overtime_table.setMaximumHeight(180)
        rl.addWidget(self._overtime_table)

        self._overtime_form = self._build_overtime_form()
        self._overtime_form.setVisible(False)
        rl.addWidget(self._overtime_form)

        splitter.addWidget(right)
        splitter.setSizes([300, 700])
        root.addWidget(splitter, 1)

    def _build_add_form(self) -> QFrame:
        """Erstellt das Formular zum Hinzufügen einer neuen Regel."""
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self._form_title_lbl = QLabel("Neue Regel hinzufügen")
        self._form_title_lbl.setObjectName("section-title")
        layout.addWidget(self._form_title_lbl)

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

        self._submit_btn = QPushButton("＋  Hinzufügen")
        self._submit_btn.setObjectName("primary")
        self._submit_btn.clicked.connect(self._add_rule)
        row3.addWidget(self._submit_btn)

        self._cancel_edit_btn = QPushButton("Abbrechen")
        self._cancel_edit_btn.setVisible(False)
        self._cancel_edit_btn.clicked.connect(self._cancel_edit)
        row3.addWidget(self._cancel_edit_btn)

        layout.addLayout(row3)

        # Initialen Scope-Zustand setzen
        self._on_scope_changed(0)
        return frame

    def _build_overtime_form(self) -> QFrame:
        """Formular zum Hinzufügen eines Überstunden-Eintrags."""
        frame = QFrame()
        frame.setObjectName("card")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Datum:"))
        self._ot_date_edit = QDateEdit()
        self._ot_date_edit.setCalendarPopup(True)
        self._ot_date_edit.setDisplayFormat("dd.MM.yyyy")
        today = date.today()
        self._ot_date_edit.setDate(QDate(today.year, today.month, today.day))
        self._ot_date_edit.setFixedWidth(130)
        layout.addWidget(self._ot_date_edit)

        layout.addWidget(QLabel("Stunden:"))
        self._ot_hours_spin = QDoubleSpinBox()
        self._ot_hours_spin.setRange(-999.0, 999.0)
        self._ot_hours_spin.setDecimals(2)
        self._ot_hours_spin.setSuffix(" h")
        self._ot_hours_spin.setFixedWidth(110)
        self._ot_hours_spin.setToolTip("Positiv = Überstunden, Negativ = Freizeitausgleich/Abzug")
        layout.addWidget(self._ot_hours_spin)

        layout.addWidget(QLabel("Notiz:"))
        self._ot_note_edit = QLineEdit()
        self._ot_note_edit.setPlaceholderText("Optional …")
        layout.addWidget(self._ot_note_edit, 1)

        save_btn = QPushButton("＋  Hinzufügen")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._add_overtime_entry)
        layout.addWidget(save_btn)

        cancel_btn = QPushButton("✕")
        cancel_btn.clicked.connect(self._toggle_overtime_form)
        layout.addWidget(cancel_btn)

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
        if self._edit_mode:
            self._set_edit_mode(False)
        if self._profile_edit_mode:
            self._cancel_profile_edit()
        if self._overtime_form.isVisible():
            self._toggle_overtime_form()
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
        self._populate_overtime_table(emp.id)

    # ------------------------------------------------------------------
    # Profil bearbeiten
    # ------------------------------------------------------------------

    def _toggle_profile_edit(self) -> None:
        if not self._profile_edit_mode:
            self._start_profile_edit()
        else:
            self._cancel_profile_edit()

    def _start_profile_edit(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        emp = self._employees[row]

        self._edit_name.setText(emp.name)

        idx = self._edit_skill.findData(emp.skill_level)
        if idx >= 0:
            self._edit_skill.setCurrentIndex(idx)

        idx = self._edit_contract.findData(emp.contract_type)
        if idx >= 0:
            self._edit_contract.setCurrentIndex(idx)

        self._edit_hours.setValue(emp.target_hours_per_month)
        self._edit_prefers_between.setChecked(bool(emp.prefers_between_shift))
        self._edit_max_late.setValue(emp.max_late_shifts_per_week or 0)

        self._profile_edit_mode = True
        self._info_frame.setVisible(False)
        self._info_edit_frame.setVisible(True)
        self._profile_edit_btn.setText("✕  Abbrechen")
        self._profile_edit_btn.setStyleSheet(
            "QPushButton { background: #B91C1C; color: #FAFAFA; border: none;"
            " font-weight: 600; border-radius: 6px; padding: 7px 16px; }"
            "QPushButton:hover { background: #991B1B; }"
        )

    def _cancel_profile_edit(self) -> None:
        self._profile_edit_mode = False
        self._info_frame.setVisible(True)
        self._info_edit_frame.setVisible(False)
        self._profile_edit_btn.setText("✏  Bearbeiten")
        self._profile_edit_btn.setStyleSheet("")

    def _save_profile(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._employees):
            return
        emp = self._employees[row]

        name = self._edit_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Pflichtfeld", "Bitte einen Namen eingeben.")
            return

        try:
            with get_session() as session:
                obj = session.get(Employee, emp.id)
                if obj:
                    obj.name = name
                    obj.skill_level = self._edit_skill.currentData()
                    obj.contract_type = self._edit_contract.currentData()
                    obj.target_hours_per_month = self._edit_hours.value()
                    obj.prefers_between_shift = self._edit_prefers_between.isChecked()
                    max_late = self._edit_max_late.value()
                    obj.max_late_shifts_per_week = max_late if max_late > 0 else None
        except Exception as exc:
            QMessageBox.warning(self, "Fehler", f"Profil konnte nicht gespeichert werden:\n{exc}")
            return

        saved_id = emp.id
        self._cancel_profile_edit()

        with get_session() as session:
            self._employees = EmployeeRepository(session).get_all()

        self._list.blockSignals(True)
        self._list.clear()
        select_row = 0
        for i, e in enumerate(self._employees):
            color = SKILL_COLOR.get(e.skill_level, "#999")
            item = QListWidgetItem(f"  {e.name}")
            item.setForeground(QBrush(QColor(color)))
            item.setToolTip(
                f"{SKILL_LABEL.get(e.skill_level, e.skill_level)} · "
                f"{CONTRACT_LABEL.get(e.contract_type, e.contract_type)}"
            )
            self._list.addItem(item)
            if e.id == saved_id:
                select_row = i
        self._list.blockSignals(False)
        self._list.setCurrentRow(select_row)
        self._show_employee(self._employees[select_row])

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
            note_text = rule.note or ""
            note_item = QTableWidgetItem(note_text)
            note_item.setToolTip(note_text)
            self._rules_table.setItem(row, 3, note_item)

            # Bearbeiten + Löschen (Spalte 4, nur in Edit-Modus sichtbar)
            rule_id = rule.id
            edit_btn = QPushButton("✏ Bearbeiten")
            edit_btn.setStyleSheet(
                "QPushButton { background: #18181B; color: #FAFAFA; border: none;"
                " border-right: 1px solid #3F3F46; border-radius: 0;"
                " font-size: 12px; padding: 0 8px; }"
                "QPushButton:hover { background: #27272A; }"
            )
            edit_btn.clicked.connect(lambda _checked, rid=rule_id: self._start_edit_rule(rid))

            del_btn = QPushButton("✕")
            del_btn.setStyleSheet(
                "QPushButton { background: #B91C1C; color: #FAFAFA; border: none;"
                " border-radius: 0; font-size: 12px; padding: 0 8px; }"
                "QPushButton:hover { background: #991B1B; }"
            )
            del_btn.clicked.connect(lambda _checked, rid=rule_id: self._delete_rule(rid))

            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(0)
            cell_layout.addWidget(edit_btn, 1)
            cell_layout.addWidget(del_btn)
            self._rules_table.setCellWidget(row, 4, cell)

    # ------------------------------------------------------------------
    # Überstundenkonto
    # ------------------------------------------------------------------

    def _populate_overtime_table(self, employee_id: int) -> None:
        with get_session() as session:
            repo = EmployeeRepository(session)
            entries = repo.get_overtime_entries(employee_id)
            total = sum(e.hours for e in entries)
            # Daten aus Session herauslösen
            data = [(e.id, e.entry_date, e.hours, e.note) for e in entries]

        color = "#166534" if total >= 0 else "#991B1B"
        self._overtime_total_lbl.setText(
            f'Gesamt: <b><span style="color:{color};">{total:+.2f} h</span></b>'
        )

        self._overtime_table.setRowCount(len(data))
        for row, (entry_id, entry_date, hours, note) in enumerate(data):
            date_item = QTableWidgetItem(entry_date.strftime("%d.%m.%Y"))
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._overtime_table.setItem(row, 0, date_item)

            hours_color = "#166534" if hours >= 0 else "#991B1B"
            hours_item = QTableWidgetItem(f"{hours:+.2f} h")
            hours_item.setForeground(QBrush(QColor(hours_color)))
            hours_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._overtime_table.setItem(row, 1, hours_item)

            note_item = QTableWidgetItem(note or "")
            note_item.setToolTip(note or "")
            self._overtime_table.setItem(row, 2, note_item)

            del_btn = QPushButton("✕")
            del_btn.setStyleSheet(
                "QPushButton { background: #B91C1C; color: #FAFAFA; border: none;"
                " border-radius: 4px; font-size: 11px; padding: 0 6px; }"
                "QPushButton:hover { background: #991B1B; }"
            )
            del_btn.clicked.connect(lambda _checked, eid=entry_id: self._delete_overtime_entry(eid))
            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(4, 2, 4, 2)
            cell_layout.addWidget(del_btn)
            self._overtime_table.setCellWidget(row, 3, cell)

    def _toggle_overtime_form(self) -> None:
        visible = not self._overtime_form.isVisible()
        self._overtime_form.setVisible(visible)
        if visible:
            self._add_overtime_btn.setText("✕  Schließen")
            self._ot_hours_spin.setValue(0.0)
            self._ot_note_edit.clear()
        else:
            self._add_overtime_btn.setText("＋  Eintrag")

    def _add_overtime_entry(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._employees):
            return
        emp = self._employees[row]

        qd = self._ot_date_edit.date()
        entry_date = date(qd.year(), qd.month(), qd.day())
        hours = self._ot_hours_spin.value()
        if hours == 0.0:
            QMessageBox.warning(self, "Ungültig", "Bitte eine Stundenzahl (≠ 0) eingeben.")
            return
        note = self._ot_note_edit.text().strip() or None

        try:
            with get_session() as session:
                entry = OvertimeEntry(
                    employee_id=emp.id,
                    entry_date=entry_date,
                    hours=hours,
                    note=note,
                )
                EmployeeRepository(session).add_overtime_entry(entry)
        except Exception as exc:
            QMessageBox.warning(self, "Fehler", f"Eintrag konnte nicht gespeichert werden:\n{exc}")
            return

        self._toggle_overtime_form()
        self._populate_overtime_table(emp.id)

    def _delete_overtime_entry(self, entry_id: int) -> None:
        confirm = QMessageBox.question(
            self, "Eintrag entfernen",
            "Diesen Überstunden-Eintrag wirklich entfernen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        row = self._list.currentRow()
        if row < 0 or row >= len(self._employees):
            return
        emp = self._employees[row]
        try:
            with get_session() as session:
                entry = session.get(OvertimeEntry, entry_id)
                if entry:
                    EmployeeRepository(session).delete_overtime_entry(entry)
        except Exception as exc:
            QMessageBox.warning(self, "Fehler", f"Eintrag konnte nicht gelöscht werden:\n{exc}")
            return
        self._populate_overtime_table(emp.id)

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
                "QPushButton { background: #18181B; color: #FAFAFA; font-weight: 600;"
                " border: none; border-radius: 6px; padding: 7px 16px; }"
                "QPushButton:hover { background: #27272A; }"
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
    # Regel bearbeiten
    # ------------------------------------------------------------------

    def _start_edit_rule(self, rule_id: int) -> None:
        emp_row = self._list.currentRow()
        if emp_row < 0:
            return
        emp = self._employees[emp_row]
        rule = next((r for r in emp.availability_rules if r.id == rule_id), None)
        if rule is None:
            return

        self._editing_rule_id = rule_id

        idx = self._type_combo.findData(rule.rule_type)
        if idx >= 0:
            self._type_combo.setCurrentIndex(idx)

        idx = self._scope_combo.findData(rule.scope)
        if idx >= 0:
            self._scope_combo.setCurrentIndex(idx)
        self._on_scope_changed(0)

        if rule.shift_type:
            idx = self._shift_combo.findData(rule.shift_type)
            if idx >= 0:
                self._shift_combo.setCurrentIndex(idx)

        if rule.day_of_week is not None:
            idx = self._day_combo.findData(rule.day_of_week)
            if idx >= 0:
                self._day_combo.setCurrentIndex(idx)

        if rule.specific_date:
            d = rule.specific_date
            self._date_edit.setDate(QDate(d.year, d.month, d.day))

        self._note_edit.setText(rule.note or "")
        self._form_title_lbl.setText("Regel bearbeiten")
        self._submit_btn.setText("✓  Speichern")
        self._cancel_edit_btn.setVisible(True)

    def _cancel_edit(self) -> None:
        self._editing_rule_id = None
        self._form_title_lbl.setText("Neue Regel hinzufügen")
        self._submit_btn.setText("＋  Hinzufügen")
        self._cancel_edit_btn.setVisible(False)
        self._note_edit.clear()

    # ------------------------------------------------------------------
    # Regel hinzufügen / speichern
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
                if self._editing_rule_id is not None:
                    old = session.get(AvailabilityRule, self._editing_rule_id)
                    if old:
                        EmployeeRepository(session).delete_rule(old)
                EmployeeRepository(session).add_rule(new_rule)
        except Exception as exc:
            QMessageBox.warning(self, "Fehler", f"Regel konnte nicht gespeichert werden:\n{exc}")
            return

        self._cancel_edit()
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
