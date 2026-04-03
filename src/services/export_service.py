"""
PDF-Export für den Schichtplan.

Seite 1 – Schichtplan-Grid (Querformat A4)
  Kopfzeile: Planungszeitraum, Generierungsdatum
  Grid: Mitarbeiter × Tage, farbige Schicht-Kürzel, Wochenenden grau
  Legende: Schichtkürzel + Zeiten, Feiertage mit *

Seite 2 – Mitarbeiter-Detailansicht
  Tabelle: Name, Qualifikation, Vertragstyp, Soll-Stunden/Monat, max. Spätschichten

Seite 3 – Stundenkonten + Auslastungsübersicht
  Pro Mitarbeiter: Soll, Ist, Urlaub, Feiertags-Bonus, Monatssaldo, Kumuliert

Footer jeder Seite: Erstellt am … | Seite X von Y
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, KeepTogether,
)
from reportlab.platypus.flowables import HRFlowable

from src.database.connection import get_session
from src.database.models import Employee, HourBalance
from src.domain.enums import ShiftType, SkillLevel, ContractType
from src.repositories.employee_repository import EmployeeRepository
from src.repositories.occupancy_repository import OccupancyRepository
from src.repositories.plan_repository import PlanRepository
from src.ui.styles import (
    SHIFT_BG, SHIFT_LABEL, SKILL_LABEL, CONTRACT_LABEL,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WEEKDAY_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
_MONTH_DE = [
    "", "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]

def _rl_color(hex_color: str) -> colors.HexColor:
    return colors.HexColor(hex_color)

def _shift_bg(shift: str) -> colors.HexColor:
    return _rl_color(SHIFT_BG.get(shift, SHIFT_BG[""]))

def _days_in_period(start: date, end: date) -> list[date]:
    days = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    return days


# ---------------------------------------------------------------------------
# ExportService
# ---------------------------------------------------------------------------

class ExportService:
    """Erstellt einen mehrseitigen PDF-Schichtplan."""

    def export_plan_pdf(self, period_id: int, path: str) -> None:
        with get_session() as session:
            plan_repo = PlanRepository(session)
            emp_repo = EmployeeRepository(session)
            occ_repo = OccupancyRepository(session)

            period = plan_repo.get_period_by_id(period_id)
            if not period:
                raise ValueError(f"Planungsperiode {period_id} nicht gefunden.")

            employees = emp_repo.get_all()
            assignments = plan_repo.get_assignments_for_period(period_id)
            days = _days_in_period(period.start_date, period.end_date)
            holiday_dates = {
                h.date for h in occ_repo.get_holidays_in_range(
                    period.start_date, period.end_date
                )
            }

            # Build lookup: (employee_id, date) → shift_type
            assign_map: dict[tuple[int, date], str] = {}
            for a in assignments:
                assign_map[(a.employee_id, a.date)] = a.shift_type

            # Build hour-balance lookup: employee_id → HourBalance
            balance_map: dict[int, HourBalance] = {}
            for emp in employees:
                # Use whichever month/year the period starts in
                bal = plan_repo.get_hour_balance(
                    emp.id, period.start_date.year, period.start_date.month
                )
                if bal:
                    balance_map[emp.id] = bal

        # --- Build PDF ---
        _PDFBuilder(
            path=path,
            period=period,
            employees=employees,
            days=days,
            assign_map=assign_map,
            balance_map=balance_map,
            holiday_dates=holiday_dates,
        ).build()


# ---------------------------------------------------------------------------
# Internal builder
# ---------------------------------------------------------------------------

class _PDFBuilder:
    # Colours
    C_HEADER     = colors.HexColor("#2C3E50")
    C_HEADER_FG  = colors.white
    C_WEEKEND    = colors.HexColor("#FFF3E0")
    C_HOLIDAY    = colors.HexColor("#FDEBD0")
    C_ALT_ROW    = colors.HexColor("#F8F9FA")
    C_GRID       = colors.HexColor("#CCCCCC")
    C_EXPERT     = colors.HexColor("#27AE60")
    C_MEDIUM     = colors.HexColor("#F39C12")
    C_BEGINNER   = colors.HexColor("#E74C3C")
    C_POS_BAL    = colors.HexColor("#27AE60")
    C_NEG_BAL    = colors.HexColor("#E74C3C")

    _SKILL_COLOR = {
        "EXPERT":   "#27AE60",
        "MEDIUM":   "#F39C12",
        "BEGINNER": "#E74C3C",
    }

    def __init__(
        self,
        path: str,
        period,
        employees: list[Employee],
        days: list[date],
        assign_map: dict[tuple[int, date], str],
        balance_map: dict[int, HourBalance],
        holiday_dates: set[date],
    ) -> None:
        self.path = path
        self.period = period
        self.employees = employees
        self.days = days
        self.assign_map = assign_map
        self.balance_map = balance_map
        self.holiday_dates = holiday_dates
        self.today_str = date.today().strftime("%d.%m.%Y")
        self._total_pages = 3   # updated after build
        self._styles = getSampleStyleSheet()

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def build(self) -> None:
        # Page 1 uses landscape A4, pages 2+3 use portrait A4.
        # We write them as separate canvases and merge via a custom approach:
        # Use ReportLab's canvas directly for page 1 (landscape grid),
        # then switch to portrait for pages 2+3 via SimpleDocTemplate.
        # Simplest cross-platform approach: write all 3 pages onto one canvas
        # that changes page size per page.

        c = Canvas(self.path)
        self._page1_grid(c)
        self._page2_employees(c)
        self._page3_balances(c)
        c.save()

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _footer(self, c: Canvas, page_num: int, total: int, width: float, height: float) -> None:
        c.saveState()
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.HexColor("#888888"))
        footer_y = 10 * mm
        c.drawString(15 * mm, footer_y, f"Erstellt am {self.today_str}")
        c.drawRightString(width - 15 * mm, footer_y, f"Seite {page_num} von {total}")
        c.line(15 * mm, footer_y + 4 * mm, width - 15 * mm, footer_y + 4 * mm)
        c.restoreState()

    def _page_title(self, c: Canvas, title: str, subtitle: str, width: float, height: float) -> float:
        """Draws title block, returns y below it."""
        c.saveState()
        c.setFillColor(self.C_HEADER)
        c.rect(0, height - 18 * mm, width, 18 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(15 * mm, height - 10 * mm, title)
        c.setFont("Helvetica", 9)
        c.drawRightString(width - 15 * mm, height - 10 * mm, subtitle)
        c.restoreState()
        return height - 22 * mm

    # ------------------------------------------------------------------
    # Page 1: Shift Grid (landscape)
    # ------------------------------------------------------------------

    def _page1_grid(self, c: Canvas) -> None:
        W, H = landscape(A4)
        c.setPageSize((W, H))

        period_label = (
            f"{self.period.start_date.strftime('%d.%m.%Y')} – "
            f"{self.period.end_date.strftime('%d.%m.%Y')}"
        )
        top_y = self._page_title(
            c,
            f"Schichtplan  {period_label}",
            f"Status: {self.period.status}",
            W, H,
        )

        # ---- Geometry ----
        LEFT = 15 * mm
        n_days = len(self.days)
        n_emps = len(self.employees)
        name_col_w = 32 * mm
        avail_w = W - LEFT - 15 * mm - name_col_w
        day_col_w = avail_w / n_days
        row_h = min(7.5 * mm, (top_y - 28 * mm - 20 * mm) / (n_emps + 1))
        row_h = max(row_h, 5 * mm)

        grid_top = top_y - 4 * mm
        SHIFT_FONT_SIZE = min(7, row_h * 0.55 / mm)
        HEADER_FONT_SIZE = min(7, row_h * 0.55 / mm)

        # ---- Day header ----
        c.saveState()
        c.setFont("Helvetica-Bold", HEADER_FONT_SIZE)
        # Name column header
        c.setFillColor(self.C_HEADER)
        c.rect(LEFT, grid_top - row_h, name_col_w, row_h, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.drawCentredString(LEFT + name_col_w / 2, grid_top - row_h + 2 * mm, "Mitarbeiter")

        for i, d in enumerate(self.days):
            x = LEFT + name_col_w + i * day_col_w
            is_weekend = d.weekday() >= 5
            is_holiday = d in self.holiday_dates
            if is_holiday:
                bg = self.C_HOLIDAY
            elif is_weekend:
                bg = self.C_WEEKEND
            else:
                bg = self.C_HEADER

            c.setFillColor(bg)
            c.rect(x, grid_top - row_h, day_col_w, row_h, fill=1, stroke=0)

            fg = colors.white if (not is_weekend and not is_holiday) else self.C_HEADER
            c.setFillColor(fg)
            label = f"{_WEEKDAY_DE[d.weekday()]}\n{d.day:02d}.{d.month:02d}"
            # Two lines manually
            c.drawCentredString(x + day_col_w / 2, grid_top - row_h + row_h * 0.55,
                                _WEEKDAY_DE[d.weekday()])
            c.drawCentredString(x + day_col_w / 2, grid_top - row_h + row_h * 0.15,
                                f"{d.day:02d}.{d.month:02d}")
        c.restoreState()

        # ---- Employee rows ----
        c.saveState()
        c.setFont("Helvetica", SHIFT_FONT_SIZE)
        for row_idx, emp in enumerate(self.employees):
            y = grid_top - (row_idx + 2) * row_h
            row_bg = self.C_ALT_ROW if row_idx % 2 == 0 else colors.white

            # Name cell
            c.setFillColor(row_bg)
            c.rect(LEFT, y, name_col_w, row_h, fill=1, stroke=0)
            skill_hex = self._SKILL_COLOR.get(emp.skill_level, "#333333")
            c.setFillColor(_rl_color(skill_hex))
            c.setFont("Helvetica-Bold", SHIFT_FONT_SIZE)
            c.drawString(LEFT + 1.5 * mm, y + row_h * 0.25, emp.name)
            c.setFont("Helvetica", SHIFT_FONT_SIZE - 0.5)
            c.setFillColor(colors.HexColor("#666666"))
            c.drawString(LEFT + 1.5 * mm, y + row_h * 0.6,
                         SKILL_LABEL.get(emp.skill_level, emp.skill_level))

            # Day cells
            for col_idx, d in enumerate(self.days):
                x = LEFT + name_col_w + col_idx * day_col_w
                shift = self.assign_map.get((emp.id, d), "")
                is_weekend = d.weekday() >= 5
                is_holiday = d in self.holiday_dates

                cell_bg: colors.Color
                if shift:
                    cell_bg = _rl_color(SHIFT_BG[shift])
                    fg_color = colors.white
                elif is_holiday:
                    cell_bg = self.C_HOLIDAY
                    fg_color = self.C_HEADER
                elif is_weekend:
                    cell_bg = self.C_WEEKEND
                    fg_color = colors.HexColor("#AAAAAA")
                else:
                    cell_bg = row_bg
                    fg_color = colors.HexColor("#CCCCCC")

                c.setFillColor(cell_bg)
                c.rect(x, y, day_col_w, row_h, fill=1, stroke=0)
                c.setFillColor(fg_color)
                c.setFont("Helvetica-Bold", SHIFT_FONT_SIZE)
                label = shift if shift else "–"
                c.drawCentredString(x + day_col_w / 2, y + row_h * 0.25, label)

            # Grid lines
            c.setStrokeColor(self.C_GRID)
            c.setLineWidth(0.3)
            c.rect(LEFT, y, name_col_w + n_days * day_col_w, row_h, fill=0, stroke=1)

        c.restoreState()

        # ---- Legend ----
        legend_y = grid_top - (n_emps + 2) * row_h - 4 * mm
        c.saveState()
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(self.C_HEADER)
        c.drawString(LEFT, legend_y, "Legende:")
        c.setFont("Helvetica", 7)
        lx = LEFT + 18 * mm
        for code, label in SHIFT_LABEL.items():
            if not code:
                continue
            c.setFillColor(_rl_color(SHIFT_BG[code]))
            c.rect(lx, legend_y - 1 * mm, 5 * mm, 4.5 * mm, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 6.5)
            c.drawCentredString(lx + 2.5 * mm, legend_y + 0.3 * mm, code)
            c.setFillColor(self.C_HEADER)
            c.setFont("Helvetica", 6.5)
            c.drawString(lx + 6.5 * mm, legend_y + 0.3 * mm, label)
            lx += 55 * mm

        # Holiday note
        if self.holiday_dates:
            c.setFont("Helvetica", 6.5)
            c.setFillColor(colors.HexColor("#888888"))
            c.drawString(LEFT, legend_y - 5 * mm,
                         "* Feiertag – Arbeit zählt als Überstunde")
        c.restoreState()

        self._footer(c, 1, 3, W, H)
        c.showPage()

    # ------------------------------------------------------------------
    # Page 2: Employee detail table (portrait)
    # ------------------------------------------------------------------

    def _page2_employees(self, c: Canvas) -> None:
        W, H = A4
        c.setPageSize((W, H))

        top_y = self._page_title(c, "Mitarbeiter-Übersicht", "", W, H)

        # Build table data
        headers = ["Name", "Qualifikation", "Vertragstyp", "Soll-Std./Mon.", "Max. Spät/Wo."]
        rows = [headers]
        for emp in self.employees:
            rows.append([
                emp.name,
                SKILL_LABEL.get(emp.skill_level, emp.skill_level),
                CONTRACT_LABEL.get(emp.contract_type, emp.contract_type),
                f"{emp.target_hours_per_month:.1f} h",
                str(emp.max_late_shifts_per_week) if emp.max_late_shifts_per_week else "–",
            ])

        col_widths = [50 * mm, 40 * mm, 40 * mm, 30 * mm, 25 * mm]
        tbl = Table(rows, colWidths=col_widths, repeatRows=1)

        # Per-row skill colour stripe
        style_cmds = [
            ("BACKGROUND",   (0, 0), (-1, 0), self.C_HEADER),
            ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 9),
            ("ALIGN",        (0, 0), (-1, -1), "LEFT"),
            ("ALIGN",        (3, 1), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, self.C_ALT_ROW]),
            ("GRID",         (0, 0), (-1, -1), 0.4, self.C_GRID),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        for i, emp in enumerate(self.employees, start=1):
            hex_c = self._SKILL_COLOR.get(emp.skill_level, "#333333")
            style_cmds.append(
                ("TEXTCOLOR", (0, i), (0, i), _rl_color(hex_c))
            )
            style_cmds.append(
                ("FONTNAME", (0, i), (0, i), "Helvetica-Bold")
            )
        tbl.setStyle(TableStyle(style_cmds))

        # Draw table manually on canvas
        avail_w = W - 30 * mm
        avail_h = top_y - 25 * mm
        tbl.wrapOn(c, avail_w, avail_h)
        tbl.drawOn(c, 15 * mm, top_y - 10 * mm - tbl._height)

        self._footer(c, 2, 3, W, H)
        c.showPage()

    # ------------------------------------------------------------------
    # Page 3: Hour balances + occupancy summary (portrait)
    # ------------------------------------------------------------------

    def _page3_balances(self, c: Canvas) -> None:
        W, H = A4
        c.setPageSize((W, H))

        period_month = f"{_MONTH_DE[self.period.start_date.month]} {self.period.start_date.year}"
        top_y = self._page_title(c, "Stundenkonten", period_month, W, H)

        headers = ["Mitarbeiter", "Soll", "Ist", "Urlaub", "Feiertag", "Saldo", "Kumuliert"]
        rows = [headers]

        for emp in self.employees:
            bal = self.balance_map.get(emp.id)
            if bal:
                soll   = f"{bal.target_hours:.1f} h"
                ist    = f"{bal.scheduled_hours:.1f} h"
                urlaub = f"{bal.vacation_hours:.1f} h"
                ftag   = f"{bal.holiday_bonus_hours:.1f} h"
                delta  = f"{bal.balance_delta:+.1f} h"
                kum    = f"{bal.cumulative_balance:+.1f} h"
            else:
                soll = ist = urlaub = ftag = delta = kum = "–"
            rows.append([emp.name, soll, ist, urlaub, ftag, delta, kum])

        col_widths = [45 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm]
        tbl = Table(rows, colWidths=col_widths, repeatRows=1)

        style_cmds = [
            ("BACKGROUND",   (0, 0), (-1, 0), self.C_HEADER),
            ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 9),
            ("ALIGN",        (0, 0), (-1, -1), "LEFT"),
            ("ALIGN",        (1, 1), (-1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, self.C_ALT_ROW]),
            ("GRID",         (0, 0), (-1, -1), 0.4, self.C_GRID),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        # Colour-code delta and cumulative columns
        for i, emp in enumerate(self.employees, start=1):
            bal = self.balance_map.get(emp.id)
            if bal:
                for col_idx in (5, 6):
                    val = bal.balance_delta if col_idx == 5 else bal.cumulative_balance
                    color = self.C_POS_BAL if val >= 0 else self.C_NEG_BAL
                    style_cmds.append(("TEXTCOLOR", (col_idx, i), (col_idx, i), color))
                    style_cmds.append(("FONTNAME", (col_idx, i), (col_idx, i), "Helvetica-Bold"))

        tbl.setStyle(TableStyle(style_cmds))

        avail_w = W - 30 * mm
        avail_h = top_y - 25 * mm
        tbl.wrapOn(c, avail_w, avail_h)
        tbl.drawOn(c, 15 * mm, top_y - 10 * mm - tbl._height)

        # ---- Occupancy summary ----
        occ_top = top_y - 10 * mm - tbl._height - 12 * mm
        c.saveState()
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(self.C_HEADER)
        c.drawString(15 * mm, occ_top, "Belegungsübersicht")
        c.setLineWidth(0.5)
        c.setStrokeColor(self.C_HEADER)
        c.line(15 * mm, occ_top - 1.5 * mm, W - 15 * mm, occ_top - 1.5 * mm)
        c.restoreState()

        # Count shifts per day
        occ_y = occ_top - 8 * mm
        col_w = min(10 * mm, (W - 30 * mm) / len(self.days))
        c.saveState()
        c.setFont("Helvetica-Bold", 6.5)
        c.setFillColor(self.C_HEADER)
        # Headers
        x = 15 * mm
        c.drawString(x, occ_y + 3 * mm, "Datum")
        x += 20 * mm
        for d in self.days:
            is_weekend = d.weekday() >= 5
            is_holiday = d in self.holiday_dates
            if is_weekend or is_holiday:
                c.setFillColor(colors.HexColor("#CC6600"))
            else:
                c.setFillColor(self.C_HEADER)
            c.drawCentredString(x + col_w / 2, occ_y + 3 * mm,
                                f"{d.day:02d}.{d.month:02d}")
            x += col_w

        # Shift rows
        for shift_code in ("F", "Z", "S", "N"):
            occ_y -= 6 * mm
            x = 15 * mm
            c.setFillColor(self.C_HEADER)
            c.setFont("Helvetica-Bold", 6.5)
            c.drawString(x, occ_y, SHIFT_LABEL.get(shift_code, shift_code)[:12])
            x += 20 * mm
            for d in self.days:
                count = sum(
                    1 for emp in self.employees
                    if self.assign_map.get((emp.id, d)) == shift_code
                )
                bg = _rl_color(SHIFT_BG[shift_code])
                c.setFillColor(bg)
                c.rect(x, occ_y - 0.5 * mm, col_w - 0.5 * mm, 5 * mm, fill=1, stroke=0)
                c.setFillColor(colors.white if count else colors.HexColor("#AAAAAA"))
                c.setFont("Helvetica-Bold" if count else "Helvetica", 6)
                c.drawCentredString(x + col_w / 2, occ_y + 0.8 * mm, str(count) if count else "–")
                x += col_w

        c.restoreState()

        self._footer(c, 3, 3, W, H)
        c.showPage()
