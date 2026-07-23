import csv
import io
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors as rl_colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QComboBox, QDateEdit, QFileDialog,
    QGraphicsDropShadowEffect, QMessageBox, QDialog, QSizePolicy,
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QColor

NAVY = "#1B3A5C"
STEEL = "#4A7FB5"
WHITE = "#FFFFFF"
CARD_BG = "#F8F9FB"
TEXT_DARK = "#1A1A2E"
TEXT_GRAY = "#6B7280"
GREEN = "#059669"
AMBER = "#D97706"
RED = "#DC2626"
BORDER = "#E5E7EB"

PALETTE = [NAVY, STEEL, GREEN, AMBER, RED, "#8B5CF6", "#EC4899"]

sns.set_theme(style="whitegrid", palette=PALETTE)

CHART_TYPES = {
    "cases_by_status": ["Bar", "Pie"],
    "cases_by_type": ["Pie", "Bar"],
    "appointments": ["Bar", "Pie"],
    "trends": ["Line", "Bar"],
}

DEFAULT_CHARTS = {
    "cases_by_status": "Bar",
    "cases_by_type": "Pie",
    "appointments": "Bar",
    "trends": "Line",
}


def _parse_date(date_str):
    try:
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None


def _filter_cases(cases, date_from, date_to, case_type):
    result = cases
    if case_type and case_type != "All":
        result = [c for c in result if c.get("case_type") == case_type]
    if date_from or date_to:
        filtered = []
        for c in result:
            created = _parse_date(c.get("created_at", ""))
            if created is None:
                continue
            if date_from and created < date_from:
                continue
            if date_to and created > date_to:
                continue
            filtered.append(c)
        result = filtered
    return result


def _filter_invoices(invoices, date_from, date_to):
    result = invoices
    if date_from or date_to:
        filtered = []
        for inv in result:
            created = _parse_date(inv.get("created_at", ""))
            if created is None:
                continue
            if date_from and created < date_from:
                continue
            if date_to and created > date_to:
                continue
            filtered.append(inv)
        result = filtered
    return result


def _filter_appointments(appts, date_from, date_to):
    result = appts
    if date_from or date_to:
        filtered = []
        for a in result:
            d = _parse_date(a.get("date", ""))
            if d is None:
                continue
            if date_from and d < date_from:
                continue
            if date_to and d > date_to:
                continue
            filtered.append(a)
        result = filtered
    return result


class StatCardWidget(QFrame):
    def __init__(self, title, value="—", color=TEXT_DARK, parent=None):
        super().__init__(parent)
        self.setFixedHeight(100)
        self.setMinimumWidth(160)
        self.setStyleSheet(f"""
            StatCardWidget {{ background-color: {WHITE}; border: 1px solid {BORDER};
                             border-radius: 10px; }}
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        self._title_lbl = QLabel(title)
        self._title_lbl.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 12px; border: none;")
        self._value_lbl = QLabel(str(value))
        self._value_lbl.setStyleSheet(f"color: {color}; font-size: 26px; font-weight: bold; border: none;")
        layout.addWidget(self._title_lbl)
        layout.addStretch()
        layout.addWidget(self._value_lbl)

    def set_value(self, value):
        self._value_lbl.setText(str(value))


def _chart_widget(fig):
    canvas = FigureCanvasQTAgg(fig)
    canvas.setMinimumHeight(320)
    canvas.setFocusPolicy(Qt.NoFocus)
    canvas.wheelEvent = lambda e: e.ignore()
    canvas.setStyleSheet(f"border: 1px solid {BORDER}; border-radius: 8px; background: {WHITE};")
    return canvas


def _make_figure():
    fig, ax = plt.subplots(figsize=(8, 3.2))
    fig.patch.set_facecolor(WHITE)
    ax.set_facecolor(WHITE)
    return fig, ax


class _ChartPanel(QFrame):
    chart_type_changed = Signal(str)
    export_requested = Signal()
    expand_requested = Signal()

    def __init__(self, title, metric_key, parent=None):
        super().__init__(parent)
        self._metric_key = metric_key
        self._title = title
        self.setStyleSheet("background: transparent; border: none;")
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(4)

        header = QHBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        header.addWidget(title_lbl)

        types = CHART_TYPES.get(metric_key, ["Bar"])
        self._type_combo = QComboBox()
        self._type_combo.addItems(types)
        self._type_combo.setCurrentText(DEFAULT_CHARTS.get(metric_key, types[0]))
        self._type_combo.setStyleSheet(f"""
            QComboBox {{ padding: 2px 6px; border: 1px solid {BORDER}; border-radius: 4px;
                         font-size: 11px; color: {TEXT_DARK}; background: {WHITE}; }}
        """)
        self._type_combo.currentTextChanged.connect(
            lambda t: self.chart_type_changed.emit(t)
        )
        header.addWidget(QLabel("Chart:"))
        header.addWidget(self._type_combo)

        export_btn = QPushButton("Export")
        export_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {STEEL}; border: none;"
                                 f" font-size: 11px; padding: 2px 8px; }}"
                                 f"QPushButton:hover {{ text-decoration: underline; }}")
        export_btn.clicked.connect(lambda: self.export_requested.emit())
        header.addWidget(export_btn)
        header.addStretch()
        self._outer.addLayout(header)

        self._canvas_container = QVBoxLayout()
        self._outer.addLayout(self._canvas_container)
        self._canvas_widget = None

    def set_canvas(self, widget):
        while self._canvas_container.count():
            item = self._canvas_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if widget:
            widget.setCursor(Qt.PointingHandCursor)
            widget.setToolTip("Click to expand")
            orig = widget.mouseReleaseEvent
            panel = self
            def on_click(e):
                panel.expand_requested.emit()
                if orig:
                    return orig(e)
            widget.mouseReleaseEvent = on_click
            self._canvas_container.addWidget(widget)
            self._canvas_widget = widget

    def chart_type(self):
        return self._type_combo.currentText()

    def title(self):
        return self._title


class LawyerReportsPage(QWidget):
    def __init__(self, repo, user, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._user = user
        self._date_from = None
        self._date_to = None
        self._case_type = "All"
        self._panels = {}
        self._chart_figures = {}
        self._all_widgets = []
        self._stat_cards = []
        self._content_layout = None
        self._filtered_cases = []
        self._build()
        self.refresh()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._build_filter_bar(outer)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        scroll.setFocusPolicy(Qt.StrongFocus)
        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(24, 16, 24, 24)
        self._content_layout.setSpacing(16)
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _build_filter_bar(self, outer):
        bar = QFrame()
        bar.setStyleSheet(f"background: {WHITE}; border-bottom: 1px solid {BORDER};")
        bar.setFixedHeight(52)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(16, 8, 16, 8)
        bar_layout.setSpacing(8)

        heading = QLabel("Reports")
        heading.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        bar_layout.addWidget(heading)
        bar_layout.addSpacing(16)

        self._range_combo = QComboBox()
        self._range_combo.addItems(["Last 30 days", "Last 90 days", "Last year", "All time", "Custom"])
        self._range_combo.setStyleSheet(f"""
            QComboBox {{ padding: 4px 8px; border: 1px solid {BORDER}; border-radius: 4px;
                         font-size: 12px; color: {TEXT_DARK}; background: {WHITE}; }}
        """)
        self._range_combo.currentTextChanged.connect(self._on_range_changed)
        bar_layout.addWidget(QLabel("Period:"))
        bar_layout.addWidget(self._range_combo)

        self._from_date = QDateEdit()
        self._from_date.setCalendarPopup(True)
        self._from_date.setDate(QDate.currentDate().addMonths(-1))
        self._from_date.setStyleSheet(f"padding: 3px 6px; border: 1px solid {BORDER}; border-radius: 4px; font-size: 12px;")
        self._from_date.setVisible(False)
        bar_layout.addWidget(self._from_date)

        self._to_date = QDateEdit()
        self._to_date.setCalendarPopup(True)
        self._to_date.setDate(QDate.currentDate())
        self._to_date.setStyleSheet(f"padding: 3px 6px; border: 1px solid {BORDER}; border-radius: 4px; font-size: 12px;")
        self._to_date.setVisible(False)
        bar_layout.addWidget(self._to_date)

        bar_layout.addSpacing(8)
        bar_layout.addWidget(QLabel("Type:"))
        self._type_combo = QComboBox()
        self._type_combo.addItems(["All", "criminal", "civil", "corporate", "family"])
        self._type_combo.setStyleSheet(f"""
            QComboBox {{ padding: 4px 8px; border: 1px solid {BORDER}; border-radius: 4px;
                         font-size: 12px; color: {TEXT_DARK}; background: {WHITE}; }}
        """)
        self._type_combo.currentTextChanged.connect(self._on_filter_changed)
        bar_layout.addWidget(self._type_combo)

        bar_layout.addStretch()

        cases_csv_btn = QPushButton("Export Cases CSV")
        cases_csv_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {STEEL};"
                                    f" border: 1px solid {STEEL}; border-radius: 4px;"
                                    f" padding: 6px 12px; font-size: 11px; font-weight: bold; }}"
                                    f"QPushButton:hover {{ background: {STEEL}; color: {WHITE}; }}")
        cases_csv_btn.clicked.connect(self._export_cases_csv)
        bar_layout.addWidget(cases_csv_btn)

        cases_pdf_btn = QPushButton("Export Cases PDF")
        cases_pdf_btn.setStyleSheet(f"QPushButton {{ background: {STEEL}; color: {WHITE}; border: none;"
                                    f" border-radius: 4px; padding: 6px 12px; font-size: 11px; font-weight: bold; }}"
                                    f"QPushButton:hover {{ background: {NAVY}; }}")
        cases_pdf_btn.clicked.connect(self._export_cases_pdf)
        bar_layout.addWidget(cases_pdf_btn)

        csv_btn = QPushButton("Export Stats CSV")
        csv_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {GREEN}; border: 1px solid {GREEN};"
                              f" border-radius: 4px; padding: 6px 12px; font-size: 11px; font-weight: bold; }}"
                              f"QPushButton:hover {{ background: {GREEN}; color: {WHITE}; }}")
        csv_btn.clicked.connect(self._export_csv)
        bar_layout.addWidget(csv_btn)

        pdf_btn = QPushButton("Export Stats PDF")
        pdf_btn.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none;"
                              f" border-radius: 4px; padding: 6px 12px; font-size: 11px; font-weight: bold; }}"
                              f"QPushButton:hover {{ background: {STEEL}; }}")
        pdf_btn.clicked.connect(self._export_pdf)
        bar_layout.addWidget(pdf_btn)

        outer.addWidget(bar)

    def _on_range_changed(self, text):
        if text == "Custom":
            self._from_date.setVisible(True)
            self._to_date.setVisible(True)
        else:
            self._from_date.setVisible(False)
            self._to_date.setVisible(False)
        self.refresh()

    def _on_filter_changed(self):
        self.refresh()

    def _resolve_date_range(self):
        text = self._range_combo.currentText()
        today = datetime.now()
        if text == "Last 30 days":
            return (today - timedelta(days=30)), today
        elif text == "Last 90 days":
            return (today - timedelta(days=90)), today
        elif text == "Last year":
            return (today - timedelta(days=365)), today
        elif text == "Custom":
            qd_from = self._from_date.date()
            qd_to = self._to_date.date()
            return (datetime(qd_from.year(), qd_from.month(), qd_from.day()),
                    datetime(qd_to.year(), qd_to.month(), qd_to.day(), 23, 59, 59))
        return None, None

    def refresh(self):
        self._clear_content()
        self._date_from, self._date_to = self._resolve_date_range()
        self._case_type = self._type_combo.currentText()
        if self._case_type == "All":
            self._case_type = ""

        uid = self._user["user_id"]
        all_unfiltered = self._repo.get_cases_for_lawyer(uid)
        cases = _filter_cases(all_unfiltered, self._date_from, self._date_to, self._case_type)
        self._filtered_cases = cases
        appts = self._repo.get_appointments_for_lawyer(uid)
        appts = _filter_appointments(appts, self._date_from, self._date_to)

        all_cases = _filter_cases(
            all_unfiltered, self._date_from, self._date_to, self._case_type
        ) if (self._date_from or self._date_to or self._case_type) else all_unfiltered

        self._add_stat_cards(cases)
        self._add_panel("Cases by Status", "cases_by_status",
                        _render_cases_by_status, cases, None, None)
        self._add_panel("Cases by Type", "cases_by_type",
                        _render_cases_by_type, cases, None, None)
        self._add_panel("Appointment Statistics", "appointments",
                        _render_appointments, appts, None, None)
        self._add_panel("Cases Opened Over Time", "trends",
                        _render_trends, all_cases, None, None)
        self._content_layout.addStretch()

    def _clear_content(self):
        for widget in self._all_widgets:
            widget.deleteLater()
        self._all_widgets.clear()
        self._panels.clear()
        self._chart_figures.clear()
        self._stat_cards.clear()
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_stat_cards(self, cases):
        row = QHBoxLayout()
        row.setSpacing(16)

        total = len(cases)
        c1 = StatCardWidget("Total Cases", str(total), NAVY)
        self._stat_cards.append((c1, "Total Cases", str(total)))
        row.addWidget(c1)
        self._all_widgets.append(c1)

        closed = [c for c in cases if c.get("status") == "Closed"]
        rate = f"{(len(closed) / len(cases) * 100):.1f}%" if cases else "—"
        c2 = StatCardWidget("Closing Rate", rate, GREEN)
        self._stat_cards.append((c2, "Closing Rate", rate))
        row.addWidget(c2)
        self._all_widgets.append(c2)

        closed_dates = [
            _parse_date(c.get("created_at", ""))
            for c in cases if c.get("status") == "Closed"
        ]
        if closed_dates:
            now = datetime.now()
            avg_days = sum((now - d).days for d in closed_dates if d) / len(closed_dates)
            avg_str = f"{avg_days:.0f} days"
        else:
            avg_str = "—"
        c3 = StatCardWidget("Avg Time to Close", avg_str, AMBER)
        self._stat_cards.append((c3, "Avg Time to Close", avg_str))
        row.addWidget(c3)
        self._all_widgets.append(c3)

        row.addStretch()
        self._content_layout.addLayout(row)

    def _add_panel(self, title, metric_key, render_fn, data1, data2, data3):
        panel = _ChartPanel(title, metric_key)
        self._panels[metric_key] = panel
        self._all_widgets.append(panel)

        def refresh_chart(chart_type=None):
            if chart_type is None:
                chart_type = panel.chart_type()
            fig = render_fn(chart_type, data1, data2, data3)
            self._chart_figures[metric_key] = fig
            canvas = _chart_widget(fig)
            self._all_widgets.append(canvas)
            panel.set_canvas(canvas)

        def export_this_chart():
            path, _ = QFileDialog.getSaveFileName(
                self, f"Export {title}", f"{metric_key}.png",
                "PNG (*.png);;PDF (*.pdf)"
            )
            if not path:
                return
            fig = self._chart_figures.get(metric_key)
            if fig is None:
                return
            if path.lower().endswith(".pdf"):
                with tempfile.TemporaryDirectory() as tmpdir:
                    png_path = os.path.join(tmpdir, "chart.png")
                    fig.savefig(png_path, dpi=150, bbox_inches="tight",
                               facecolor=WHITE, edgecolor="none")
                    doc = SimpleDocTemplate(path, pagesize=landscape(A4),
                                            leftMargin=36, rightMargin=36,
                                            topMargin=36, bottomMargin=36)
                    styles = getSampleStyleSheet()
                    elements = [
                        Paragraph(title, styles["Title"]),
                        Spacer(1, 12),
                        Image(png_path, width=9 * inch, height=4 * inch),
                    ]
                    doc.build(elements)
            else:
                fig.savefig(path, dpi=150, bbox_inches="tight",
                           facecolor=WHITE, edgecolor="none")

        panel.chart_type_changed.connect(refresh_chart)
        panel.export_requested.connect(export_this_chart)

        def show_expanded():
            fig = self._chart_figures.get(metric_key)
            if fig is None:
                return
            dlg = QDialog(self)
            dlg.setWindowTitle(title)
            dlg.resize(960, 620)
            dlg.setMinimumSize(700, 480)
            dlg.setStyleSheet(f"background: {WHITE};")
            dlg_layout = QVBoxLayout(dlg)
            dlg_layout.setContentsMargins(12, 12, 12, 12)
            dlg_layout.setSpacing(6)

            ch_header = QHBoxLayout()
            ch_title = QLabel(title)
            ch_title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT_DARK}; border: none;")
            ch_header.addWidget(ch_title)
            types = CHART_TYPES.get(metric_key, ["Bar"])
            ch_combo = QComboBox()
            ch_combo.addItems(types)
            ch_combo.setCurrentText(panel.chart_type())
            ch_combo.setStyleSheet(f"""
                QComboBox {{ padding: 3px 8px; border: 1px solid {BORDER}; border-radius: 4px;
                             font-size: 12px; color: {TEXT_DARK}; background: {WHITE}; }}
            """)
            ch_header.addWidget(QLabel("Chart:"))
            ch_header.addWidget(ch_combo)
            ch_header.addStretch()

            ch_export = QPushButton("Export")
            ch_export.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none;"
                                    f" border-radius: 4px; padding: 5px 14px; font-size: 11px; font-weight: bold; }}"
                                    f"QPushButton:hover {{ background: {STEEL}; }}")
            ch_export.clicked.connect(lambda: export_this_chart())
            ch_header.addWidget(ch_export)
            dlg_layout.addLayout(ch_header)

            big_fig = render_fn(panel.chart_type(), data1, data2, data3)
            big_canvas = FigureCanvasQTAgg(big_fig)
            big_canvas.setFocusPolicy(Qt.NoFocus)
            big_canvas.setStyleSheet(f"border: 1px solid {BORDER}; border-radius: 6px; background: {WHITE};")
            dlg_layout.addWidget(big_canvas, stretch=1)

            def on_type_change(t):
                new_fig = render_fn(t, data1, data2, data3)
                for i in reversed(range(dlg_layout.count())):
                    item = dlg_layout.itemAt(i)
                    if item.widget() and isinstance(item.widget(), FigureCanvasQTAgg):
                        item.widget().deleteLater()
                new_canvas = FigureCanvasQTAgg(new_fig)
                new_canvas.setFocusPolicy(Qt.NoFocus)
                new_canvas.setStyleSheet(f"border: 1px solid {BORDER}; border-radius: 6px; background: {WHITE};")
                dlg_layout.addWidget(new_canvas, stretch=1)

            ch_combo.currentTextChanged.connect(on_type_change)
            dlg.exec()

        panel.expand_requested.connect(show_expanded)
        refresh_chart(panel.chart_type())
        self._content_layout.addWidget(panel)

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Stats CSV", "report_stats.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Metric", "Value"])
        for _card, title, value in self._stat_cards:
            writer.writerow([title, value])
        writer.writerow([])
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write(output.getvalue())

    def _export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Stats PDF", "report_stats.pdf", "PDF Files (*.pdf)"
        )
        if not path:
            return
        doc = SimpleDocTemplate(path, pagesize=A4,
                                leftMargin=36, rightMargin=36,
                                topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph("Engaz — Lawyer Report", styles["Title"]))
        elements.append(Spacer(1, 12))
        period = self._range_combo.currentText()
        elements.append(Paragraph(f"Period: {period}", styles["Normal"]))
        elements.append(Spacer(1, 12))

        stat_data = [["Metric", "Value"]]
        for _card, title, value in self._stat_cards:
            stat_data.append([title, str(value)])
        table = Table(stat_data, colWidths=[3 * inch, 2 * inch])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor(NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.HexColor(BORDER)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 16))

        with tempfile.TemporaryDirectory() as tmpdir:
            for metric_key, fig in self._chart_figures.items():
                png_path = os.path.join(tmpdir, f"{metric_key}.png")
                fig.savefig(png_path, dpi=120, bbox_inches="tight",
                           facecolor=WHITE, edgecolor="none")
                img = Image(png_path, width=6.5 * inch, height=2.8 * inch)
                elements.append(img)
                elements.append(Spacer(1, 10))
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                styles["Italic"],
            ))
            doc.build(elements)

    def _export_cases_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export All Cases CSV", "all_cases.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        uid = self._user["user_id"]
        all_cases = self._repo.get_cases_for_lawyer(uid)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Case #", "Title", "Type", "Status", "Client", "Date Created"])
        for case in all_cases:
            client = self._repo.get_user(case.get("client_id", ""))
            client_name = f"{client['first_name']} {client['last_name']}" if client else "—"
            writer.writerow([
                case.get("case_number", ""),
                case.get("title", ""),
                case.get("case_type", ""),
                case.get("status", ""),
                client_name,
                (case.get("created_at", "")[:10]) if case.get("created_at") else "",
            ])
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write(output.getvalue())

    def _export_cases_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export All Cases PDF", "all_cases.pdf", "PDF Files (*.pdf)"
        )
        if not path:
            return
        uid = self._user["user_id"]
        all_cases = self._repo.get_cases_for_lawyer(uid)
        doc = SimpleDocTemplate(path, pagesize=landscape(A4),
                                leftMargin=24, rightMargin=24,
                                topMargin=24, bottomMargin=24)
        styles = getSampleStyleSheet()
        elements = []
        elements.append(Paragraph("Engaz — All Cases", styles["Title"]))
        elements.append(Spacer(1, 8))
        elements.append(Paragraph(
            f"Lawyer: {self._user['first_name']} {self._user['last_name']}",
            styles["Normal"],
        ))
        elements.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  "
            f"Total cases: {len(all_cases)}",
            styles["Normal"],
        ))
        elements.append(Spacer(1, 12))

        data = [["Case #", "Title", "Type", "Status", "Client", "Date"]]
        for case in all_cases:
            client = self._repo.get_user(case.get("client_id", ""))
            client_name = f"{client['first_name']} {client['last_name']}" if client else "—"
            data.append([
                case.get("case_number", ""),
                case.get("title", ""),
                case.get("case_type", ""),
                case.get("status", ""),
                client_name,
                (case.get("created_at", "")[:10]) if case.get("created_at") else "",
            ])
        col_widths = [1.0 * inch, 3.5 * inch, 1.2 * inch, 1.2 * inch, 2.0 * inch, 1.2 * inch]
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor(NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.HexColor(BORDER)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor("#F8F9FB")]),
        ]))
        elements.append(table)
        doc.build(elements)


# ── Chart rendering functions (chart_type, data1, data2, data3) ──────

def _render_cases_by_status(chart_type, cases, _d2, _d3):
    counts = defaultdict(int)
    for c in cases:
        counts[c.get("status", "Unknown")] += 1
    statuses = ["Open", "In Progress", "Closed"]
    values = [counts.get(s, 0) for s in statuses]
    colors = [STEEL, AMBER, GREEN]

    fig, ax = _make_figure()
    if chart_type == "Pie":
        non_zero = [(s, v, cl) for s, v, cl in zip(statuses, values, colors) if v > 0]
        if non_zero:
            labels = [x[0] for x in non_zero]
            vals = [x[1] for x in non_zero]
            cls = [x[2] for x in non_zero]
            wedges, texts, autotexts = ax.pie(
                vals, labels=labels, autopct="%1.1f%%", colors=cls,
                startangle=140, textprops={"fontsize": 10, "color": TEXT_DARK},
            )
            for at in autotexts:
                at.set_color(WHITE)
                at.set_fontweight("bold")
    else:
        bars = ax.bar(statuses, values, color=colors, edgecolor="none")
        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                        str(val), ha="center", fontsize=11, fontweight="bold", color=TEXT_DARK)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    ax.set_title("Cases by Status", fontsize=14, fontweight="bold", color=TEXT_DARK, pad=10)
    ax.tick_params(colors=TEXT_GRAY, labelsize=10)
    fig.tight_layout()
    return fig


def _render_cases_by_type(chart_type, cases, _d2, _d3):
    counts = defaultdict(int)
    for c in cases:
        ct = c.get("case_type", "other")
        counts[ct.capitalize()] += 1
    colors_l = [NAVY, STEEL, GREEN, AMBER, "#8B5CF6"]

    fig, ax = _make_figure()
    if not counts:
        ax.set_title("Cases by Type", fontsize=14, fontweight="bold", color=TEXT_DARK, pad=10)
        fig.tight_layout()
        return fig

    labels = list(counts.keys())
    values = list(counts.values())

    if chart_type == "Bar":
        bars = ax.bar(labels, values, color=colors_l[:len(labels)], edgecolor="none")
        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                        str(val), ha="center", fontsize=10, fontweight="bold", color=TEXT_DARK)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    else:
        wedges, texts, autotexts = ax.pie(
            values, labels=labels, autopct="%1.1f%%", colors=colors_l[:len(labels)],
            startangle=140, textprops={"fontsize": 10, "color": TEXT_DARK},
        )
        for at in autotexts:
            at.set_color(WHITE)
            at.set_fontweight("bold")
    ax.set_title("Cases by Type", fontsize=14, fontweight="bold", color=TEXT_DARK, pad=10)
    ax.tick_params(colors=TEXT_GRAY, labelsize=10)
    fig.tight_layout()
    return fig


def _render_appointments(chart_type, appts, _d2, _d3):
    counts = defaultdict(int)
    for a in appts:
        counts[a.get("status", "Unknown")] += 1
    labels = ["Requested", "Approved", "Completed", "Declined", "Cancelled"]
    values = [counts.get(l, 0) for l in labels]
    colors_l = [AMBER, STEEL, GREEN, RED, TEXT_GRAY]

    fig, ax = _make_figure()
    if chart_type == "Pie":
        non_zero = [(l, v, cl) for l, v, cl in zip(labels, values, colors_l) if v > 0]
        if non_zero:
            lbs = [x[0] for x in non_zero]
            vls = [x[1] for x in non_zero]
            cls = [x[2] for x in non_zero]
            wedges, texts, autotexts = ax.pie(
                vls, labels=lbs, autopct="%1.1f%%", colors=cls,
                startangle=140, textprops={"fontsize": 9, "color": TEXT_DARK},
            )
            for at in autotexts:
                at.set_color(WHITE)
                at.set_fontweight("bold")
    else:
        bars = ax.bar(labels, values, color=colors_l, edgecolor="none")
        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                        str(val), ha="center", fontsize=10, fontweight="bold", color=TEXT_DARK)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    ax.set_title("Appointment Statistics", fontsize=14, fontweight="bold", color=TEXT_DARK, pad=10)
    ax.tick_params(colors=TEXT_GRAY, labelsize=9)
    fig.tight_layout()
    return fig


def _render_trends(chart_type, all_cases, _d2, _d3):
    cases_by_month = defaultdict(int)
    for c in all_cases:
        d = _parse_date(c.get("created_at", ""))
        if d:
            cases_by_month[d.strftime("%Y-%m")] += 1

    fig, ax = _make_figure()
    if not cases_by_month:
        ax.set_title("Cases Opened Over Time", fontsize=14, fontweight="bold", color=TEXT_DARK, pad=10)
        fig.tight_layout()
        return fig

    months = sorted(cases_by_month.keys())
    values = [cases_by_month[m] for m in months]
    x = range(len(months))

    if chart_type == "Bar":
        bars = ax.bar(x, values, color=STEEL, edgecolor="none")
        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                        str(val), ha="center", fontsize=10, fontweight="bold", color=TEXT_DARK)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    else:
        ax.fill_between(x, values, alpha=0.2, color=STEEL)
        ax.plot(x, values, marker="o", color=STEEL, linewidth=2)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    ax.set_xticks(x)
    xticks = months if len(months) <= 12 else [months[i] for i in range(0, len(months), max(1, len(months) // 12))]
    if len(months) > 12:
        ax.set_xticks(range(0, len(months), max(1, len(months) // 12)))
    ax.set_xticklabels(xticks, rotation=45, ha="right", fontsize=9)
    ax.set_title("Cases Opened Over Time", fontsize=14, fontweight="bold", color=TEXT_DARK, pad=10)
    ax.tick_params(colors=TEXT_GRAY, labelsize=9)
    fig.tight_layout()
    return fig
