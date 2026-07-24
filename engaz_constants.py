from datetime import datetime

from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt

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
    "invoice_created": PAGE_INVOICES,
    "invoice_paid": PAGE_INVOICES,
    "message_received": PAGE_MESSAGES,
    "case_created": PAGE_CASES,
}


def _status_badge(status_text):
    colors = {
        "Open": (STEEL, WHITE),
        "In Progress": (AMBER, WHITE),
        "Closed": (TEXT_GRAY, WHITE),
        "Approved": (GREEN, WHITE),
        "Requested": (AMBER, WHITE),
        "Declined": (RED, WHITE),
        "Completed": (STEEL, WHITE),
        "Cancelled": (TEXT_GRAY, WHITE),
        "Pending": (AMBER, WHITE),
        "Paid": (GREEN, WHITE),
        "Overdue": (RED, WHITE),
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


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            clear_layout(item.layout())
