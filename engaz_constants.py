from datetime import datetime

from PySide6.QtWidgets import (
    QLabel, QComboBox, QLineEdit, QTextEdit, QSpinBox, QDateEdit,
    QStyledItemDelegate, QStyle, QApplication, QWidget,
)
from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QPainter, QFont, QColor, QPen, QBrush, QPalette

# ── Standard Colors ───────────────────────────────────────────────────────
NAVY = "#1B3A5C"
STEEL = "#4A7FB5"
WHITE = "#FFFFFF"
LIGHT_GRAY = "#F5F6FA"
CARD_BG = "#F8F9FB"
TEXT_DARK = "#1A1A2E"
TEXT_GRAY = "#6B7280"
GREEN = "#059669"
AMBER = "#D97706"
RED = "#DC2626"
BORDER = "#E5E7EB"

# ── Page indices (for sidebar and notification navigation) ────────────────
PAGE_DASHBOARD = 0
PAGE_CASES = 1
PAGE_CALENDAR = 2
PAGE_INVOICES = 3
PAGE_MESSAGES = 4
PAGE_REPORTS = 5
PAGE_LAW_LIBRARY = 6
PAGE_STAKEHOLDER_DASHBOARD = 7

NOTIFICATION_PAGE = {
    "appointment_requested": PAGE_CALENDAR,
    "appointment_approved": PAGE_CALENDAR,
    "appointment_declined": PAGE_CALENDAR,
    "appointment_completed": PAGE_CALENDAR,
    "appointment_cancelled": PAGE_CALENDAR,
    "invoice_created": PAGE_INVOICES,
    "invoice_paid": PAGE_INVOICES,
    "invoice_overdue": PAGE_INVOICES,
    "message_received": PAGE_MESSAGES,
    "case_created": PAGE_CASES,
    "case_attachment_added": PAGE_CASES,
}


def _status_badge(status_text):
    colors = {
        "Open": (STEEL, WHITE),
        "In Progress": (AMBER, WHITE),
        "On Hold": (TEXT_GRAY, WHITE),
        "Closed": (TEXT_GRAY, WHITE),
        "Won": (GREEN, WHITE),
        "Lost": (RED, WHITE),
        "Approved": (GREEN, WHITE),
        "Requested": (AMBER, WHITE),
        "Declined": (RED, WHITE),
        "Completed": (STEEL, WHITE),
        "Cancelled": (TEXT_GRAY, WHITE),
        "No Show": (RED, WHITE),
        "Pending": (AMBER, WHITE),
        "Paid": (GREEN, WHITE),
        "Overdue": (RED, WHITE),
        "Draft": (TEXT_GRAY, WHITE),
        "Sent": (STEEL, WHITE),
        "Partially Paid": (AMBER, WHITE),
    }
    bg, fg = colors.get(status_text, (TEXT_GRAY, WHITE))
    lbl = QLabel(status_text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(
        f"background: {bg}; color: {fg}; padding: 2px 10px; "
        f"border-radius: 10px; font-size: 11px; font-weight: bold;"
    )
    return lbl


def _format_time(iso_string):
    try:
        dt = datetime.fromisoformat(iso_string)
        now = datetime.now()
        if dt.date() == now.date():
            return dt.strftime("%I:%M %p")
        return dt.strftime("%b %d, %Y")
    except (ValueError, TypeError):
        return ""


# ── Global QSS Stylesheet ─────────────────────────────────────────────────

GLOBAL_QSS = """
/* ── Inputs ───────────────────────────────────── */
QLineEdit, QTextEdit, QSpinBox {
    padding: 8px 12px;
    border: 1px solid """ + BORDER + """;
    border-radius: 6px;
    background: """ + WHITE + """;
    color: """ + TEXT_DARK + """;
    font-size: 13px;
    selection-background-color: """ + STEEL + """;
    selection-color: """ + WHITE + """;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus {
    border: 1.5px solid """ + STEEL + """;
}
QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled {
    background: """ + LIGHT_GRAY + """;
    color: """ + TEXT_GRAY + """;
}

QDateEdit {
    padding: 8px 28px 8px 12px;
    border: 1px solid """ + BORDER + """;
    border-radius: 6px;
    background: """ + WHITE + """;
    color: """ + TEXT_DARK + """;
    font-size: 13px;
    selection-background-color: """ + STEEL + """;
    selection-color: """ + WHITE + """;
}
QDateEdit:focus {
    border: 1.5px solid """ + STEEL + """;
}
QDateEdit:disabled {
    background: """ + LIGHT_GRAY + """;
    color: """ + TEXT_GRAY + """;
}

/* ── ComboBox ─────────────────────────────────── */
QComboBox {
    padding: 8px 28px 8px 12px;
    border: 1px solid """ + BORDER + """;
    border-radius: 6px;
    background: """ + WHITE + """;
    color: """ + TEXT_DARK + """;
    font-size: 13px;
}
QComboBox:focus {
    border: 1.5px solid """ + STEEL + """;
}
QComboBox:disabled {
    background: """ + LIGHT_GRAY + """;
    color: """ + TEXT_GRAY + """;
}
QComboBox QAbstractItemView {
    border: 1px solid """ + BORDER + """;
    border-radius: 6px;
    padding: 4px;
    outline: none;
    selection-background-color: """ + NAVY + """;
    selection-color: """ + WHITE + """;
    background: """ + WHITE + """;
}

/* ── Table ────────────────────────────────────── */
QTableWidget {
    border: 1px solid """ + BORDER + """;
    border-radius: 6px;
    gridline-color: """ + BORDER + """;
    background: """ + WHITE + """;
    alternate-background-color: """ + CARD_BG + """;
    selection-background-color: """ + STEEL + """;
    selection-color: """ + WHITE + """;
    font-size: 13px;
}
QTableWidget::item {
    padding: 10px;
}
QHeaderView::section {
    background: """ + NAVY + """;
    color: """ + WHITE + """;
    padding: 10px;
    font-weight: bold;
    font-size: 12px;
    border: none;
    border-right: 1px solid rgba(255, 255, 255, 0.15);
}

/* ── Buttons ──────────────────────────────────── */
QPushButton {
    padding: 8px 20px;
    border-radius: 6px;
    font-weight: bold;
    font-size: 13px;
    min-height: 36px;
}
QPushButton:disabled {
    opacity: 0.5;
}

/* ── ScrollArea ───────────────────────────────── */
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    width: 8px;
    background: transparent;
    border: none;
}
QScrollBar::handle:vertical {
    background: rgba(0, 0, 0, 0.1);
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(0, 0, 0, 0.2);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    height: 8px;
    background: transparent;
    border: none;
}
QScrollBar::handle:horizontal {
    background: rgba(0, 0, 0, 0.1);
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: rgba(0, 0, 0, 0.2);
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── Dialog ───────────────────────────────────── */
QDialog {
    background: """ + WHITE + """;
}

/* ── Label ────────────────────────────────────── */
QLabel {
    color: """ + TEXT_DARK + """;
}
"""

# ── Button QSS presets ──────────────────────────────────────────────────────

BTN_PRIMARY = (
    f"background: {NAVY}; color: {WHITE}; "
    f"border: none; "
    f"padding: 8px 20px; border-radius: 6px; "
    f"font-weight: bold; font-size: 13px; min-height: 36px;"
)

BTN_SECONDARY = (
    f"background: {LIGHT_GRAY}; color: {TEXT_DARK}; "
    f"border: 1px solid {BORDER}; "
    f"padding: 8px 20px; border-radius: 6px; "
    f"font-weight: bold; font-size: 13px; min-height: 36px;"
)

BTN_DESTRUCTIVE = (
    f"background: {RED}; color: {WHITE}; "
    f"border: none; "
    f"padding: 8px 20px; border-radius: 6px; "
    f"font-weight: bold; font-size: 13px; min-height: 36px;"
)

# ── Hover stylesheets ───────────────────────────────────────────────────────

BTN_PRIMARY_HOVER = (
    f"QPushButton {{ {BTN_PRIMARY} }}"
    f"QPushButton:hover {{ background: {STEEL}; }}"
)
BTN_SECONDARY_HOVER = (
    f"QPushButton {{ {BTN_SECONDARY} }}"
    f"QPushButton:hover {{ background: {BORDER}; }}"
)
BTN_DESTRUCTIVE_HOVER = (
    f"QPushButton {{ {BTN_DESTRUCTIVE} }}"
    f"QPushButton:hover {{ background: #B91C1C; }}"
)

# ── ArrowComboBox ───────────────────────────────────────────────────────────

class ArrowComboBox(QComboBox):
    """QComboBox with a custom-painted chevron arrow and styled popup."""

    _ARROW_COLOR = QColor(TEXT_GRAY)
    _ARROW_HOVER_COLOR = QColor(STEEL)
    _ARROW_SIZE = 10

    def __init__(self, parent=None, placeholder="Select..."):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self._hovered = False
        self.setMouseTracking(True)
        super().setStyleSheet(self._arrow_hiding_rules())
        self._apply_popup_style()
        self.currentIndexChanged.connect(lambda _: self._on_index_changed())
        self.installEventFilter(self)

    def _arrow_hiding_rules(self):
        return ("QComboBox::drop-down { width: 0px; border: none; background: transparent; }"
                "QComboBox::down-arrow { image: none; }")

    def setStyleSheet(self, stylesheet):
        sheet = stylesheet or ""
        if "down-arrow" not in sheet:
            sheet += self._arrow_hiding_rules()
        super().setStyleSheet(sheet)

    def _apply_popup_style(self):
        self.view().window().setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = self._ARROW_HOVER_COLOR if self._hovered else self._ARROW_COLOR
        painter.setPen(QPen(color, 2))
        painter.setBrush(QBrush(color))
        right_margin = 12
        arrow_left = self.width() - right_margin - self._ARROW_SIZE
        arrow_top = (self.height() - self._ARROW_SIZE // 2) // 2
        points = [
            QPoint(arrow_left, arrow_top),
            QPoint(arrow_left + self._ARROW_SIZE, arrow_top),
            QPoint(arrow_left + self._ARROW_SIZE // 2, arrow_top + self._ARROW_SIZE // 2),
        ]
        painter.drawPolygon(points)
        painter.end()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def eventFilter(self, obj, event):
        return super().eventFilter(obj, event)

    def _on_index_changed(self):
        pass


# ── ArrowDateEdit ───────────────────────────────────────────────────────────

class ArrowDateEdit(QDateEdit):
    """QDateEdit with a custom-painted chevron arrow (matches ArrowComboBox)."""

    _ARROW_COLOR = QColor(TEXT_GRAY)
    _ARROW_HOVER_COLOR = QColor(STEEL)
    _ARROW_SIZE = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hovered = False
        self.setMouseTracking(True)
        self.setCalendarPopup(True)
        super().setStyleSheet(self._arrow_hiding_rules())
        self.installEventFilter(self)

    def _arrow_hiding_rules(self):
        return ("QAbstractSpinBox::drop-down { border: none; background: transparent; }"
                "QAbstractSpinBox::down-arrow { image: none; width: 0px; }")

    def setStyleSheet(self, stylesheet):
        sheet = stylesheet or ""
        if "down-arrow" not in sheet:
            sheet += self._arrow_hiding_rules()
        super().setStyleSheet(sheet)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = self._ARROW_HOVER_COLOR if self._hovered else self._ARROW_COLOR
        painter.setPen(QPen(color, 2))
        painter.setBrush(QBrush(color))
        right_margin = 12
        arrow_left = self.width() - right_margin - self._ARROW_SIZE
        arrow_top = (self.height() - self._ARROW_SIZE // 2) // 2
        points = [
            QPoint(arrow_left, arrow_top),
            QPoint(arrow_left + self._ARROW_SIZE, arrow_top),
            QPoint(arrow_left + self._ARROW_SIZE // 2, arrow_top + self._ARROW_SIZE // 2),
        ]
        painter.drawPolygon(points)
        painter.end()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)


# ── Required Label Helper ───────────────────────────────────────────────────

def create_required_label(label_text):
    """Return HTML-formatted label text with a red asterisk."""
    return (
        f'{label_text} '
        f'<span style="color: {RED}; font-weight: bold;">*</span>'
    )


# ── Validation Highlight Helpers ────────────────────────────────────────────

_INVALID_STYLE = f"border: 2px solid {RED};"


def highlight_invalid_input(widget):
    """Apply a red border highlight to an invalid input widget."""
    if isinstance(widget, ArrowComboBox):
        return
    current = widget.styleSheet()
    if _INVALID_STYLE in current:
        return
    widget.setStyleSheet(current + _INVALID_STYLE)


def clear_input_highlights(*widgets):
    """Remove red border highlights from one or more widgets."""
    for widget in widgets:
        if isinstance(widget, ArrowComboBox):
            continue
        current = widget.styleSheet()
        cleaned = current.replace(_INVALID_STYLE, "")
        widget.setStyleSheet(cleaned)


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            clear_layout(item.layout())


def _client_display_name(user):
    if not user:
        return "\u2014"
    if user.get("client_type") == "corporate":
        org = user.get("organization_name", "")
        if org:
            return org
    return f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "\u2014"
