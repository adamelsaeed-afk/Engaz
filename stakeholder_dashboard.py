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

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QFileDialog, QCheckBox,
    QGraphicsDropShadowEffect, QGridLayout, QSizePolicy, QDialog,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from engaz_constants import (
    NAVY, STEEL, WHITE, CARD_BG, TEXT_DARK, TEXT_GRAY,
    GREEN, AMBER, RED, BORDER, clear_layout,
    ArrowComboBox, GLOBAL_QSS, BTN_PRIMARY_HOVER, BTN_SECONDARY_HOVER,
)

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors as rl_colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet

from engaz_constants import (
    NAVY, STEEL, WHITE, CARD_BG, TEXT_DARK, TEXT_GRAY,
    GREEN, AMBER, RED, BORDER, clear_layout,
)

sns.set_theme(style="whitegrid")

ALL_METRIC_IDS = [
    "closing_rate", "revenue", "cases_by_status", "cases_by_department",
    "top_lawyers_closing", "top_lawyers_revenue", "workload",
    "appointments", "client_trends", "case_win_loss", "overdue_invoices",
]

METRIC_LABELS = {
    "closing_rate": "Closing Rate",
    "revenue": "Revenue Overview",
    "cases_by_status": "Cases by Status",
    "cases_by_department": "Cases by Department",
    "top_lawyers_closing": "Top Lawyers (Closing Rate)",
    "top_lawyers_revenue": "Top Lawyers (Revenue)",
    "workload": "Lawyer Workload",
    "appointments": "Appointment Completion",
    "client_trends": "Client Acquisition",
    "case_win_loss": "Case Win / Loss",
    "overdue_invoices": "Overdue Invoices",
}


def _parse_date(date_str):
    try:
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None


def _make_figure(figsize=(8, 3.2)):
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor(WHITE)
    ax.set_facecolor(WHITE)
    return fig, ax


def _chart_canvas(fig):
    canvas = FigureCanvasQTAgg(fig)
    canvas.setMinimumHeight(280)
    canvas.setFocusPolicy(Qt.NoFocus)
    canvas.wheelEvent = lambda e: e.ignore()
    canvas.setStyleSheet(f"border: 1px solid {BORDER}; border-radius: 6px; background: {WHITE};")
    return canvas


class _MetricWidget(QFrame):
    move_up = Signal(str)
    move_down = Signal(str)
    expand_requested = Signal(str)

    def __init__(self, metric_id, title, parent=None):
        super().__init__(parent)
        self.metric_id = metric_id
        self._title = title
        self.setStyleSheet(f"background: {WHITE}; border: 1px solid {BORDER}; border-radius: 8px;")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(6)
        shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 20))
        self.setGraphicsEffect(shadow)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(10, 4, 10, 4)
        tl = QLabel(title)
        tl.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {TEXT_DARK}; border: none;")
        header.addWidget(tl)
        header.addStretch()
        up_btn = QPushButton("\u25b2")
        up_btn.setFixedSize(24, 22)
        up_btn.setStyleSheet(f"QPushButton {{ border: none; color: {TEXT_GRAY}; font-size: 10px; background: transparent; }}"
                             f"QPushButton:hover {{ color: {NAVY}; }}")
        up_btn.clicked.connect(lambda: self.move_up.emit(self.metric_id))
        header.addWidget(up_btn)
        down_btn = QPushButton("\u25bc")
        down_btn.setFixedSize(24, 22)
        down_btn.setStyleSheet(f"QPushButton {{ border: none; color: {TEXT_GRAY}; font-size: 10px; background: transparent; }}"
                               f"QPushButton:hover {{ color: {NAVY}; }}")
        down_btn.clicked.connect(lambda: self.move_down.emit(self.metric_id))
        header.addWidget(down_btn)
        self._outer.addLayout(header)

        self._content = QVBoxLayout()
        self._content.setContentsMargins(8, 0, 8, 8)
        self._outer.addLayout(self._content)

    def set_content(self, widget):
        while self._content.count():
            item = self._content.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if widget:
            widget.setCursor(Qt.PointingHandCursor)
            widget.setToolTip("Click to expand")
            mid = self.metric_id
            orig = widget.mouseReleaseEvent

            def on_click(e):
                self.expand_requested.emit(mid)
                if orig:
                    return orig(e)

            widget.mouseReleaseEvent = on_click
            self._content.addWidget(widget)


class StakeholderDashboardPage(QWidget):
    def __init__(self, repo, user, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._user = user
        self._scope = "Entire Firm"
        self._visible = list(ALL_METRIC_IDS)
        self._layout_order = list(ALL_METRIC_IDS)
        self._widgets = {}
        self._chart_figures = {}
        self._build()
        self.refresh()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._build_filter_bar(outer)

        self._settings_panel = QFrame()
        self._settings_panel.setStyleSheet(f"background: {CARD_BG}; border-bottom: 1px solid {BORDER};")
        self._settings_panel.setVisible(False)
        settings_layout = QVBoxLayout(self._settings_panel)
        settings_layout.setContentsMargins(16, 8, 16, 8)
        settings_layout.setSpacing(4)
        settings_layout.addWidget(QLabel("Toggle Metrics:"))
        settings_layout.itemAt(settings_layout.count() - 1).widget().setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {TEXT_DARK}; border: none;"
        )
        self._checkboxes = {}
        cb_grid = QGridLayout()
        for i, mid in enumerate(ALL_METRIC_IDS):
            cb = QCheckBox(METRIC_LABELS[mid])
            cb.setStyleSheet(f"font-size: 12px; color: {TEXT_DARK};")
            cb.setChecked(True)
            cb.toggled.connect(lambda checked, m=mid: self._on_metric_toggled(m, checked))
            self._checkboxes[mid] = cb
            cb_grid.addWidget(cb, i // 3, i % 3)
        settings_layout.addLayout(cb_grid)
        outer.addWidget(self._settings_panel)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(20, 16, 20, 24)
        self._content_layout.setSpacing(12)
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _build_filter_bar(self, outer):
        bar = QFrame()
        bar.setStyleSheet(f"background: {WHITE}; border-bottom: 1px solid {BORDER};")
        bar.setFixedHeight(48)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 8, 16, 8)
        bl.setSpacing(8)

        heading = QLabel("Firm Dashboard")
        heading.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        bl.addWidget(heading)
        bl.addSpacing(16)

        bl.addWidget(QLabel("Scope:"))
        self._scope_combo = ArrowComboBox(placeholder="Select scope...")
        self._populate_scope()
        self._scope_combo.setStyleSheet(GLOBAL_QSS)
        self._scope_combo.currentTextChanged.connect(self._on_scope_changed)
        bl.addWidget(self._scope_combo)

        bl.addStretch()

        gear_btn = QPushButton("\u2699")
        gear_btn.setFixedSize(32, 32)
        gear_btn.setStyleSheet(f"QPushButton {{ border: none; font-size: 18px; color: {TEXT_GRAY}; background: transparent; }}"
                               f"QPushButton:hover {{ color: {NAVY}; }}")
        gear_btn.clicked.connect(self._toggle_settings)
        bl.addWidget(gear_btn)

        pdf_btn = QPushButton("Export PDF")
        pdf_btn.setStyleSheet(BTN_PRIMARY_HOVER)
        pdf_btn.clicked.connect(self._export_pdf)
        bl.addWidget(pdf_btn)

        outer.addWidget(bar)

    def _populate_scope(self):
        self._scope_combo.clear()
        self._scope_combo.addItem("Entire Firm")
        self._scope_combo.addItem("Criminal Department")
        self._scope_combo.addItem("Civil Department")
        self._scope_combo.addItem("Corporate Department")
        self._scope_combo.addItem("Family Department")
        lawyers = self._repo.get_all_lawyers()
        for l in lawyers:
            self._scope_combo.addItem(f"{l['first_name']} {l['last_name']}", l["user_id"])

    def _toggle_settings(self):
        self._settings_panel.setVisible(not self._settings_panel.isVisible())

    def _on_metric_toggled(self, metric_id, visible):
        if visible and metric_id not in self._visible:
            self._visible.append(metric_id)
        elif not visible and metric_id in self._visible:
            self._visible.remove(metric_id)
        self._save_preferences()
        self.refresh()

    def _on_scope_changed(self):
        self._scope = self._scope_combo.currentText()
        self.refresh()

    def _save_preferences(self):
        self._repo.update_user_preferences(self._user["user_id"], {
            "visible_metrics": self._visible,
            "layout_order": self._layout_order,
        })

    def _load_preferences(self):
        prefs = self._repo.get_user_preferences(self._user["user_id"])
        if prefs:
            stored = prefs.get("visible_metrics", [])
            if stored:
                self._visible = [m for m in stored if m in ALL_METRIC_IDS]
            stored_order = prefs.get("layout_order", [])
            if stored_order:
                self._layout_order = [m for m in stored_order if m in ALL_METRIC_IDS]
            for m in ALL_METRIC_IDS:
                if m not in self._layout_order:
                    self._layout_order.append(m)

    def refresh(self):
        self._load_preferences()
        for fig in self._chart_figures.values():
            plt.close(fig)
        self._chart_figures.clear()
        self._widgets.clear()
        clear_layout(self._content_layout)

        data = self._compute_data()
        for mid in self._layout_order:
            if mid not in self._visible:
                continue
            widget = self._render_metric(mid, data)
            if widget:
                self._widgets[mid] = widget
                widget.move_up.connect(self._on_move_up)
                widget.move_down.connect(self._on_move_down)
                self._content_layout.addWidget(widget)
        self._content_layout.addStretch()

        for mid, cb in self._checkboxes.items():
            cb.setChecked(mid in self._visible)

    def _on_move_up(self, metric_id):
        idx = self._layout_order.index(metric_id)
        if idx > 0:
            self._layout_order[idx], self._layout_order[idx - 1] = \
                self._layout_order[idx - 1], self._layout_order[idx]
            self._save_preferences()
            self.refresh()

    def _on_move_down(self, metric_id):
        idx = self._layout_order.index(metric_id)
        if idx < len(self._layout_order) - 1:
            self._layout_order[idx], self._layout_order[idx + 1] = \
                self._layout_order[idx + 1], self._layout_order[idx]
            self._save_preferences()
            self.refresh()

    def _compute_data(self):
        scope = self._scope
        all_cases = self._repo.get_all_cases()
        all_invoices = self._repo.get_all_invoices()
        all_appts = self._repo.get_all_appointments()
        lawyers = self._repo.get_all_lawyers()

        if scope == "Criminal Department":
            all_cases = [c for c in all_cases if c.get("case_type") == "criminal"]
        elif scope == "Civil Department":
            all_cases = [c for c in all_cases if c.get("case_type") == "civil"]
        elif scope == "Corporate Department":
            all_cases = [c for c in all_cases if c.get("case_type") == "corporate"]
        elif scope == "Family Department":
            all_cases = [c for c in all_cases if c.get("case_type") == "family"]
        else:
            lawyer_id = self._scope_combo.currentData()
            if lawyer_id:
                all_cases = [c for c in all_cases if c.get("lawyer_id") == lawyer_id]
                all_invoices = [inv for inv in all_invoices if inv.get("lawyer_id") == lawyer_id]
                all_appts = [a for a in all_appts if a.get("lawyer_id") == lawyer_id]

        scoped_case_ids = {c["case_id"] for c in all_cases}
        if scope != "Entire Firm" and self._scope_combo.currentData():
            pass
        elif scope.startswith(("Criminal", "Civil", "Corporate", "Family")):
            all_invoices = [inv for inv in all_invoices if inv.get("case_id", "") in scoped_case_ids]
            all_appts = [a for a in all_appts if a.get("case_id", "") in scoped_case_ids]

        return {
            "cases": all_cases,
            "invoices": all_invoices,
            "appointments": all_appts,
            "lawyers": lawyers,
        }

    def _render_metric(self, mid, data):
        fn = {
            "closing_rate": self._render_closing_rate,
            "revenue": self._render_revenue,
            "cases_by_status": self._render_cases_by_status,
            "cases_by_department": self._render_cases_by_department,
            "top_lawyers_closing": self._render_top_lawyers_closing,
            "top_lawyers_revenue": self._render_top_lawyers_revenue,
            "workload": self._render_workload,
            "appointments": self._render_appointments,
            "client_trends": self._render_client_trends,
            "case_win_loss": self._render_case_win_loss,
            "overdue_invoices": self._render_overdue_invoices,
        }.get(mid)
        if fn:
            widget = _MetricWidget(mid, METRIC_LABELS[mid])
            fig = fn(data)
            self._chart_figures[mid] = fig
            canvas = _chart_canvas(fig)
            widget.set_content(canvas)
            widget.expand_requested.connect(lambda m=mid: self._expand_metric(m))
            return widget
        return None

    def _expand_metric(self, mid):
        data = self._compute_data()
        fn = {
            "closing_rate": self._render_closing_rate,
            "revenue": self._render_revenue,
            "cases_by_status": self._render_cases_by_status,
            "cases_by_department": self._render_cases_by_department,
            "top_lawyers_closing": self._render_top_lawyers_closing,
            "top_lawyers_revenue": self._render_top_lawyers_revenue,
            "workload": self._render_workload,
            "appointments": self._render_appointments,
            "client_trends": self._render_client_trends,
            "case_win_loss": self._render_case_win_loss,
            "overdue_invoices": self._render_overdue_invoices,
        }.get(mid)
        if fn is None:
            return
        fig = fn(data)
        dlg = QDialog(self)
        dlg.setWindowTitle(METRIC_LABELS.get(mid, mid))
        dlg.resize(960, 640)
        dlg.setMinimumSize(700, 480)
        dlg.setStyleSheet(f"background: {WHITE};")
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(8, 8, 8, 8)
        big_canvas = FigureCanvasQTAgg(fig)
        big_canvas.setFocusPolicy(Qt.NoFocus)
        big_canvas.wheelEvent = lambda e: e.ignore()
        big_canvas.setStyleSheet(f"border: 1px solid {BORDER}; border-radius: 6px; background: {WHITE};")
        dlg_layout.addWidget(big_canvas, stretch=1)
        dlg.exec()
        plt.close(fig)

    def _render_closing_rate(self, data):
        cases = data["cases"]
        closed = sum(1 for c in cases if c.get("status") == "Closed")
        rate = f"{(closed / len(cases) * 100):.1f}%" if cases else "0%"
        fig, ax = _make_figure((4, 1.5))
        ax.axis("off")
        ax.text(0.5, 0.5, rate, transform=ax.transAxes, ha="center", va="center",
                fontsize=52, fontweight="bold", color=GREEN)
        ax.set_title("Firm-wide Closing Rate", fontsize=12, fontweight="bold", color=TEXT_DARK, pad=6)
        fig.tight_layout()
        return fig

    def _render_revenue(self, data):
        invoices = data["invoices"]
        paid = sum(inv["amount"] for inv in invoices if inv.get("status") == "Paid")
        by_month = defaultdict(float)
        for inv in invoices:
            if inv.get("status") != "Paid":
                continue
            d = _parse_date(inv.get("created_at", ""))
            if d:
                by_month[d.strftime("%Y-%m")] += inv["amount"]
        fig, ax = _make_figure()
        if by_month:
            months = sorted(by_month.keys())
            vals = [by_month[m] for m in months]
            x = range(len(months))
            ax.fill_between(x, vals, alpha=0.2, color=GREEN)
            ax.plot(x, vals, marker="o", color=GREEN, linewidth=2)
            ax.set_xticks(x)
            ax.set_xticklabels(months if len(months) <= 12 else [months[i] for i in range(0, len(months), max(1, len(months) // 12))],
                              rotation=45, ha="right", fontsize=8)
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
        ax.set_title(f"Revenue Overview — ${paid:,.0f} total paid", fontsize=12, fontweight="bold", color=TEXT_DARK, pad=8)
        ax.tick_params(colors=TEXT_GRAY, labelsize=8)
        fig.tight_layout()
        return fig

    def _render_cases_by_status(self, data):
        cases = data["cases"]
        counts = defaultdict(int)
        for c in cases:
            counts[c.get("status", "Unknown")] += 1
        statuses = ["Open", "In Progress", "Closed"]
        vals = [counts.get(s, 0) for s in statuses]
        colors = [STEEL, AMBER, GREEN]
        fig, ax = _make_figure()
        bars = ax.bar(statuses, vals, color=colors, edgecolor="none")
        for b, v in zip(bars, vals):
            if v > 0:
                ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.2,
                        str(v), ha="center", fontsize=10, fontweight="bold", color=TEXT_DARK)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_title("Cases by Status", fontsize=12, fontweight="bold", color=TEXT_DARK, pad=8)
        ax.tick_params(colors=TEXT_GRAY, labelsize=9)
        fig.tight_layout()
        return fig

    def _render_cases_by_department(self, data):
        cases = data["cases"]
        counts = defaultdict(int)
        for c in cases:
            ct = c.get("case_type", "other")
            counts[ct.capitalize()] += 1
        fig, ax = _make_figure()
        if counts:
            labels = list(counts.keys())
            vals = list(counts.values())
            clrs = [NAVY, STEEL, GREEN, AMBER, "#8B5CF6"]
            wedges, texts, autotexts = ax.pie(
                vals, labels=labels, autopct="%1.1f%%", colors=clrs[:len(labels)],
                startangle=140, textprops={"fontsize": 9, "color": TEXT_DARK},
            )
            for at in autotexts:
                at.set_color(WHITE)
                at.set_fontweight("bold")
        ax.set_title("Cases by Department", fontsize=12, fontweight="bold", color=TEXT_DARK, pad=8)
        fig.tight_layout()
        return fig

    def _render_top_lawyers_closing(self, data):
        cases = data["cases"]
        lawyers = data["lawyers"]
        lawyer_stats = {}
        for l in lawyers:
            lc = [c for c in cases if c.get("lawyer_id") == l["user_id"]]
            if lc:
                closed = sum(1 for c in lc if c.get("status") == "Closed")
                lawyer_stats[l["user_id"]] = {
                    "name": f"{l['first_name']} {l['last_name']}",
                    "rate": closed / len(lc) * 100,
                }
        sorted_items = sorted(lawyer_stats.values(), key=lambda x: x["rate"], reverse=True)
        fig, ax = _make_figure()
        if sorted_items:
            names = [s["name"] for s in sorted_items]
            rates = [s["rate"] for s in sorted_items]
            ax.barh(names, rates, color=STEEL, edgecolor="none")
            for i, (n, r) in enumerate(zip(names, rates)):
                ax.text(r + 0.5, i, f"{r:.1f}%", va="center", fontsize=9, fontweight="bold", color=TEXT_DARK)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
        ax.set_title("Top Lawyers — Closing Rate", fontsize=12, fontweight="bold", color=TEXT_DARK, pad=8)
        ax.tick_params(colors=TEXT_GRAY, labelsize=9)
        fig.tight_layout()
        return fig

    def _render_top_lawyers_revenue(self, data):
        invoices = data["invoices"]
        lawyers = data["lawyers"]
        lawyer_rev = {}
        for l in lawyers:
            rev = sum(inv["amount"] for inv in invoices
                     if inv.get("lawyer_id") == l["user_id"] and inv.get("status") == "Paid")
            if rev > 0:
                lawyer_rev[l["user_id"]] = {
                    "name": f"{l['first_name']} {l['last_name']}",
                    "revenue": rev,
                }
        sorted_items = sorted(lawyer_rev.values(), key=lambda x: x["revenue"], reverse=True)
        fig, ax = _make_figure()
        if sorted_items:
            names = [s["name"] for s in sorted_items]
            revs = [s["revenue"] for s in sorted_items]
            ax.barh(names, revs, color=GREEN, edgecolor="none")
            for i, (n, r) in enumerate(zip(names, revs)):
                ax.text(r + r * 0.01, i, f"${r:,.0f}", va="center", fontsize=9,
                        fontweight="bold", color=TEXT_DARK)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))
        ax.set_title("Top Lawyers — Revenue", fontsize=12, fontweight="bold", color=TEXT_DARK, pad=8)
        ax.tick_params(colors=TEXT_GRAY, labelsize=9)
        fig.tight_layout()
        return fig

    def _render_workload(self, data):
        cases = data["cases"]
        lawyers = data["lawyers"]
        workloads = {}
        for l in lawyers:
            active = [c for c in cases
                      if c.get("lawyer_id") == l["user_id"]
                      and c.get("status") in ("Open", "In Progress")]
            if active:
                workloads[l["user_id"]] = {
                    "name": f"{l['first_name']} {l['last_name']}",
                    "count": len(active),
                }
        sorted_items = sorted(workloads.values(), key=lambda x: x["count"], reverse=True)
        fig, ax = _make_figure()
        if sorted_items:
            names = [s["name"] for s in sorted_items]
            counts = [s["count"] for s in sorted_items]
            ax.bar(names, counts, color=AMBER, edgecolor="none")
            for b, v in zip(ax.containers[0] if ax.containers else [], counts):
                if v > 0:
                    ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.2,
                            str(v), ha="center", fontsize=10, fontweight="bold", color=TEXT_DARK)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
        ax.set_title("Lawyer Workload — Active Cases", fontsize=12, fontweight="bold", color=TEXT_DARK, pad=8)
        ax.tick_params(colors=TEXT_GRAY, labelsize=9)
        fig.tight_layout()
        return fig

    def _render_appointments(self, data):
        appts = data["appointments"]
        lawyers = data["lawyers"]
        lawyer_appts = {}
        for l in lawyers:
            la = [a for a in appts if a.get("lawyer_id") == l["user_id"]]
            if la:
                total = len(la)
                completed = sum(1 for a in la if a.get("status") == "Completed")
                lawyer_appts[l["user_id"]] = {
                    "name": f"{l['first_name']} {l['last_name']}",
                    "total": total,
                    "completed": completed,
                }
        sorted_items = sorted(lawyer_appts.values(), key=lambda x: x["total"], reverse=True)
        fig, ax = _make_figure()
        if sorted_items:
            names = [s["name"] for s in sorted_items]
            completeds = [s["completed"] for s in sorted_items]
            x = range(len(names))
            w = 0.35
            ax.bar(x, completeds, w, color=STEEL, label="Completed", edgecolor="none")
            ax.set_xticks(x)
            ax.set_xticklabels(names, rotation=45, ha="right", fontsize=8)
            ax.legend(fontsize=8)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
        ax.set_title("Appointment Completion by Lawyer", fontsize=12, fontweight="bold", color=TEXT_DARK, pad=8)
        ax.tick_params(colors=TEXT_GRAY, labelsize=9)
        fig.tight_layout()
        return fig

    def _render_client_trends(self, data):
        cases = data["cases"]
        by_month = defaultdict(int)
        for c in cases:
            d = _parse_date(c.get("created_at", ""))
            if d:
                by_month[d.strftime("%Y-%m")] += 1
        fig, ax = _make_figure()
        if by_month:
            months = sorted(by_month.keys())
            vals = [by_month[m] for m in months]
            x = range(len(months))
            ax.fill_between(x, vals, alpha=0.2, color=NAVY)
            ax.plot(x, vals, marker="o", color=NAVY, linewidth=2)
            ax.set_xticks(x)
            ax.set_xticklabels(months if len(months) <= 12 else [months[i] for i in range(0, len(months), max(1, len(months) // 12))],
                              rotation=45, ha="right", fontsize=8)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
        ax.set_title("Client Acquisition — New Cases Over Time", fontsize=12, fontweight="bold", color=TEXT_DARK, pad=8)
        ax.tick_params(colors=TEXT_GRAY, labelsize=9)
        fig.tight_layout()
        return fig

    def _render_case_win_loss(self, data):
        cases = data["cases"]
        won = sum(1 for c in cases if c.get("status") == "Won")
        lost = sum(1 for c in cases if c.get("status") == "Lost")
        closed = sum(1 for c in cases if c.get("status") == "Closed")
        total = won + lost + closed
        if total == 0:
            fig, ax = _make_figure(figsize=(7, 3.2))
            ax.text(0.5, 0.5, "No resolved cases yet", ha="center", va="center",
                    fontsize=13, color=TEXT_GRAY)
            ax.set_title("Case Win / Loss", fontsize=12, fontweight="bold", color=TEXT_DARK, pad=8)
            return fig
        labels = ["Won", "Lost", "Closed"]
        sizes = [won, lost, closed]
        colors = [GREEN, RED, STEEL]
        fig, ax = _make_figure(figsize=(7, 3.2))
        wedges, texts, autotexts = ax.pie(
            sizes, labels=None, autopct="%1.1f%%", startangle=90,
            colors=colors, pctdistance=0.75,
        )
        for at in autotexts:
            at.set_fontsize(11)
            at.set_fontweight("bold")
            at.set_color(WHITE)
        centre_circle = plt.Circle((0, 0), 0.55, fc=WHITE)
        ax.add_artist(centre_circle)
        ax.text(0, 0, str(total), ha="center", va="center", fontsize=20, fontweight="bold", color=TEXT_DARK)
        ax.legend(
            wedges, [f"{l} ({s})" for l, s in zip(labels, sizes)],
            loc="lower center", bbox_to_anchor=(0.5, -0.15), ncol=3,
            fontsize=9, frameon=False,
        )
        ax.set_title("Case Win / Loss", fontsize=12, fontweight="bold", color=TEXT_DARK, pad=8)
        fig.tight_layout()
        return fig

    def _render_overdue_invoices(self, data):
        invoices = data.get("invoices", [])
        overdue = [inv for inv in invoices if inv.get("status") == "Overdue"
                   or (inv.get("status") != "Paid" and inv.get("due_date", "") < datetime.now().strftime("%Y-%m-%d"))]
        count = len(overdue)
        total = sum(inv["amount"] - inv.get("amount_paid", 0.0) for inv in overdue)
        fig, ax = _make_figure(figsize=(7, 3.2))
        ax.axis("off")
        if count == 0:
            ax.text(0.5, 0.5, "No overdue invoices", ha="center", va="center",
                    fontsize=13, color=GREEN, fontweight="bold")
        else:
            ax.text(0.5, 0.65, str(count), ha="center", va="center",
                    fontsize=40, fontweight="bold", color=RED, transform=ax.transAxes)
            ax.text(0.5, 0.45, "overdue invoices", ha="center", va="center",
                    fontsize=14, color=TEXT_DARK, transform=ax.transAxes)
            ax.text(0.5, 0.25, f"Total Outstanding: ${total:,.2f}", ha="center", va="center",
                    fontsize=16, fontweight="bold", color=AMBER, transform=ax.transAxes)
        ax.set_title("Overdue Invoices", fontsize=12, fontweight="bold", color=TEXT_DARK, pad=8)
        fig.tight_layout()
        return fig

    def _export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Dashboard PDF", "dashboard.pdf", "PDF Files (*.pdf)"
        )
        if not path:
            return
        data = self._compute_data()
        cases = data["cases"]
        invoices = data["invoices"]
        closed = sum(1 for c in cases if c.get("status") == "Closed")
        rate = f"{(closed / len(cases) * 100):.1f}%" if cases else "0%"
        paid = sum(inv["amount"] for inv in invoices if inv.get("status") == "Paid")

        doc = SimpleDocTemplate(path, pagesize=A4,
                                leftMargin=36, rightMargin=36,
                                topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph("Engaz — Stakeholder Dashboard", styles["Title"]))
        elements.append(Spacer(1, 8))
        elements.append(Paragraph(f"Scope: {self._scope}", styles["Normal"]))
        elements.append(Spacer(1, 12))

        stat_data = [
            ["Metric", "Value"],
            ["Closing Rate", rate],
            ["Total Revenue (Paid)", f"${paid:,.0f}"],
            ["Total Cases", str(len(cases))],
            ["Total Appointments", str(len(data["appointments"]))],
        ]
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
            for mid in self._layout_order:
                if mid not in self._visible:
                    continue
                fig = self._chart_figures.get(mid)
                if fig is None:
                    continue
                png_path = os.path.join(tmpdir, f"{mid}.png")
                fig.savefig(png_path, dpi=120, bbox_inches="tight",
                           facecolor=WHITE, edgecolor="none")
                label = METRIC_LABELS.get(mid, mid)
                elements.append(Paragraph(label, styles["Heading3"]))
                elements.append(Image(png_path, width=6.5 * inch, height=2.8 * inch))
                elements.append(Spacer(1, 10))
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                styles["Italic"],
            ))
            doc.build(elements)
