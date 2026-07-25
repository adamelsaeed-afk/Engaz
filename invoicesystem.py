#!/usr/bin/env python3
"""Engaz — Legal Management System"""

import sys
import json
import os
import calendar
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QApplication, QWidget, QFrame, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QScrollArea, QComboBox, QListView, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QDialog, QDialogButtonBox, QTextEdit,
    QStylePainter, QStyleOptionComboBox, QStyle, QDateEdit, QCheckBox,
)
from PySide6.QtCore import Qt, Signal, QPoint, QDate, QTimer, QEvent
from PySide6.QtGui import QColor, QPalette, QPainter
from PySide6.QtWidgets import QGraphicsDropShadowEffect

from engaz_constants import (
    NAVY, STEEL, WHITE, LIGHT_GRAY, CARD_BG, TEXT_DARK, TEXT_GRAY,
    GREEN, AMBER, RED, BORDER,
    PAGE_DASHBOARD, PAGE_CASES, PAGE_CALENDAR, PAGE_INVOICES,
    PAGE_MESSAGES, PAGE_REPORTS, PAGE_LAW_LIBRARY, PAGE_STAKEHOLDER_DASHBOARD,
    NOTIFICATION_PAGE, _status_badge, clear_layout,
)

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "engaz_data.json")


def _minutes_since_midnight(time_str):
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


class ArrowComboBox(QComboBox):
    """Combo box with a reliable text-based down-arrow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(False)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setView(QListView())
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QComboBox::drop-down { border: none; background: transparent; }
            QComboBox::down-arrow { image: none; }
        """)

    def paintEvent(self, event):
        """Custom paint event to draw the combo box with a text-based arrow."""
        painter = QStylePainter(self)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        option.subControls = QStyle.SC_ComboBoxFrame
        painter.drawComplexControl(QStyle.CC_ComboBox, option)

        text_rect = self.rect().adjusted(8, 0, -24, 0)
        painter.drawItemText(
            text_rect,
            Qt.AlignVCenter | Qt.AlignLeft,
            self.palette(),
            self.isEnabled(),
            self.currentText(),
        )

        arrow_rect = self.rect().adjusted(self.rect().width() - 24, 0, -6, 0)
        painter.setPen(self.palette().color(QPalette.Text))
        painter.drawText(arrow_rect, Qt.AlignCenter, "▼")


class LeftAlignedDateEdit(QDateEdit):
    """QDateEdit whose calendar popup opens aligned to the left of the widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCalendarPopup(True)
        cal = self.calendarWidget()
        if cal:
            cal.installEventFilter(self)
        self._retry_count = 0

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show:
            self._retry_count = 0
            QTimer.singleShot(0, self._reposition_calendar)
        return super().eventFilter(obj, event)

    def _reposition_calendar(self):
        cal = self.calendarWidget()
        if not cal:
            return
        w = cal.window()
        if not w or not w.isVisible() or w is self.window():
            return
        global_pos = self.mapToGlobal(self.rect().bottomLeft())
        target_x = global_pos.x() - w.width() + self.width()
        target_y = global_pos.y()
        if w.x() != target_x or w.y() != target_y:
            w.move(target_x, target_y)
        if self._retry_count < 30:
            self._retry_count += 1
            QTimer.singleShot(50, self._reposition_calendar)


# ═══════════════════════════════════════════════════════════════════════════
# Data Layer
# ═══════════════════════════════════════════════════════════════════════════

class DataRepository:
    """a JSON file database that gets updated with every cycle of the program. It contains all the data for users, cases, appointments, invoices, and notifications."""

    def __init__(self):
        self._filepath = DATA_FILE
        self._data = {}
        self._init_storage()

    def _init_storage(self):
        if os.path.exists(self._filepath):
            self._load()
            self._migrate()
        else:
            self._seed_and_save()

    def _load(self):
        with open(self._filepath, "r", encoding="utf-8") as f:
            self._data = json.load(f)

    def _migrate(self):
        changed = False
        for key in ("case_files", "law_books", "book_comments", "book_chats"):
            if key not in self._data:
                self._data[key] = []
                changed = True
        stakeholder = next(
            (u for u in self._data.get("users", []) if u.get("role") == "stakeholder"),
            None,
        )
        if stakeholder is None:
            self._data.setdefault("users", []).append({
                "user_id": "user_8",
                "username": "ahmad.al-rashid",
                "password": "stakeholder123",
                "role": "stakeholder",
                "first_name": "Ahmad",
                "last_name": "Al-Rashid",
                "email": "ahmad@engaz.com",
                "phone": "0501234567",
                "dashboard_preferences": {
                    "visible_metrics": ["closing_rate", "revenue", "cases_by_status",
                                         "cases_by_department", "top_lawyers_closing",
                                         "top_lawyers_revenue", "workload",
                                         "appointments", "client_trends"],
                    "layout_order": ["closing_rate", "revenue", "cases_by_status",
                                     "cases_by_department", "top_lawyers_closing",
                                     "top_lawyers_revenue", "workload",
                                     "appointments", "client_trends"],
                },
            })
            changed = True
        if self._deduplicate_ids():
            changed = True
        if changed:
            self._save()

    def _deduplicate_ids(self):
        changed = False
        prefix_map = {
            "appointments": "app",
            "invoices": "inv",
            "messages": "msg",
            "book_comments": "bcomment",
            "notifications": "notification",
            "cases": "case",
            "case_files": "file",
            "law_books": "book",
            "book_chats": "bchat",
        }
        notif_type_map = {
            "appointments": [
                "appointment_requested", "appointment_approved", "appointment_declined",
                "appointment_completed", "appointment_cancelled",
            ],
            "invoices": ["invoice_created", "invoice_paid"],
            "messages": ["message_received"],
        }
        for collection_key in list(self._data.keys()):
            if collection_key.startswith("_") or collection_key == "users":
                continue
            items = self._data[collection_key]
            if not items or not isinstance(items, list):
                continue
            id_candidates = [k for k in items[0].keys() if k.endswith("_id")]
            if not id_candidates:
                continue
            id_field = id_candidates[0]
            prefix = prefix_map.get(collection_key)
            if not prefix:
                continue
            seen = {}
            duplicates = []
            for item in items:
                id_val = item[id_field]
                if id_val in seen:
                    duplicates.append(item)
                else:
                    seen[id_val] = item
            if not duplicates:
                continue
            for dup_item in duplicates:
                old_id = dup_item[id_field]
                new_id = self._next_id(collection_key, prefix)
                dup_item[id_field] = new_id
                changed = True
            if changed and collection_key in notif_type_map:
                allowed_types = notif_type_map[collection_key]
                for notif in self._data.get("notifications", []):
                    if notif.get("notification_type") not in allowed_types:
                        continue
        return changed

    def _save(self):
        self._validate_no_duplicate_ids()
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def _validate_no_duplicate_ids(self):
        for collection_key, items in self._data.items():
            if collection_key.startswith("_") or not isinstance(items, list) or not items:
                continue
            id_candidates = [k for k in items[0].keys() if k.endswith("_id")]
            if not id_candidates:
                continue
            id_field = id_candidates[0]
            seen = set()
            for item in items:
                id_val = item.get(id_field)
                if id_val in seen:
                    raise RuntimeError(
                        f"Duplicate {id_field}='{id_val}' detected in '{collection_key}' "
                        f"during save — data integrity violation"
                    )
                seen.add(id_val)

    def _seed_and_save(self):
        """builds seed data and saves it in the JSON file, when the file doesn't exist"""
        self._data = _build_seed_data()
        self._save()

    def reset_to_defaults(self):
        if os.path.exists(self._filepath):
            os.remove(self._filepath)
        self._seed_and_save()

    # ── Id generators ────────────────────────────────────────────────────

    def _next_id(self, collection_key, prefix):
        items = self._data.get(collection_key, [])
        id_field = None
        if items:
            for k in items[0].keys():
                if k.endswith("_id"):
                    id_field = k
                    break
        if not id_field:
            id_field = f"{prefix}_id"
        highest = 0
        for item in items:
            cid = item.get(id_field, "")
            tail = cid.removeprefix(f"{prefix}_")
            if tail.isdigit():
                highest = max(highest, int(tail))
        candidate_num = highest + 1
        while True:
            candidate = f"{prefix}_{candidate_num}"
            if not any(item.get(id_field) == candidate for item in items):
                return candidate
            candidate_num += 1

    # ── User methods for credentials─────────────────────────────────────────────────────

    def find_user_by_credentials(self, username, password):
        for u in self._data["users"]:
            if u["username"] == username and u["password"] == password:
                return dict(u)
        return None

    def get_user(self, user_id):
        for u in self._data["users"]:
            if u["user_id"] == user_id:
                return dict(u)
        return None

    def get_all_lawyers(self):
        return [dict(u) for u in self._data["users"] if u["role"] == "lawyer"]

    def get_all_clients(self):
        return [dict(u) for u in self._data["users"] if u["role"] == "client"]

    # ── all case methods for managing cases (case creation, updates, deletion) ─────────────────────────────────────────────────────

    def get_cases_for_lawyer(self, lawyer_id):
        return [dict(c) for c in self._data["cases"] if c["lawyer_id"] == lawyer_id]

    def get_cases_for_client(self, client_id):
        return [dict(c) for c in self._data["cases"] if c["client_id"] == client_id]

    def get_case(self, case_id):
        for c in self._data["cases"]:
            if c["case_id"] == case_id:
                return dict(c)
        return None

    def _next_case_number(self):
        num = self._data["_meta"]["next_case_number"]
        self._data["_meta"]["next_case_number"] = num + 1
        self._save()
        return f"CASE-{num:03d}"

    def create_case(self, case_data):
        entry = {
            "case_id": self._next_id("cases", "case"),
            "case_number": self._next_case_number(),
            "title": case_data["title"],
            "description": case_data.get("description", ""),
            "case_type": case_data["case_type"],
            "case_date": case_data.get("case_date", datetime.now().strftime("%Y-%m-%d")),
            "client_id": case_data["client_id"],
            "lawyer_id": case_data["lawyer_id"],
            "status": case_data.get("status", "Open"),
            "created_at": datetime.now().isoformat(),
        }
        self._data["cases"].append(entry)
        self._save()
        return dict(entry)

    def update_case(self, case_id, **updates):
        for i, c in enumerate(self._data["cases"]):
            if c["case_id"] == case_id:
                self._data["cases"][i].update(updates)
                self._save()
                return dict(self._data["cases"][i])
        return None
#    old delete case method 
    # def delete_case(self, case_id):
    #     before = len(self._data["cases"])
    #     self._data["cases"] = [c for c in self._data["cases"] if c["case_id"] != case_id]
    #     if len(self._data["cases"]) != before:
    #         self._save()
    #         return True
    #     return False
    # new delete case method 
    def delete_case(self, case_id):
        for i, c in enumerate(self._data["cases"]):
            if c["case_id"] == case_id:
                del self._data["cases"][i]
                self._save()
                return True
        return False

    def delete_case_with_cascade(self, case_id):
        for coll in ("appointments", "invoices", "messages", "case_files"):
            for item in self._data.get(coll, []):
                if item.get("case_id") == case_id:
                    item["case_id"] = ""
        found = False
        for i, c in enumerate(self._data["cases"]):
            if c["case_id"] == case_id:
                del self._data["cases"][i]
                found = True
                break
        if found:
            self._save()
        return found

    def count_active_cases_for_lawyer(self, lawyer_id):
        return sum(
            1 for c in self._data["cases"]
            if c["lawyer_id"] == lawyer_id and c["status"] in ("Open", "In Progress")
        )

    def count_active_cases_for_client(self, client_id):
        return sum(
            1 for c in self._data["cases"]
            if c["client_id"] == client_id and c["status"] in ("Open", "In Progress")
        )

    # ── Appointment methods ──────────────────────────────────────────────

    def get_appointments_for_lawyer(self, lawyer_id):
        return [dict(a) for a in self._data["appointments"]
                if a["lawyer_id"] == lawyer_id]

    def get_appointments_for_client(self, client_id):
        return [dict(a) for a in self._data["appointments"]
                if a["client_id"] == client_id]

    def get_appointment(self, appointment_id):
        for a in self._data["appointments"]:
            if a["appointment_id"] == appointment_id:
                return dict(a)
        return None

    def get_appointments_for_date(self, user_id, role, date_str):
        key = "lawyer_id" if role == "lawyer" else "client_id"
        return [dict(a) for a in self._data["appointments"]
                if a[key] == user_id and a["date"] == date_str]

    def create_appointment(self, data):
        entry = {
            "appointment_id": self._next_id("appointments", "app"),
            "client_id": data["client_id"],
            "lawyer_id": data["lawyer_id"],
            "case_id": data.get("case_id", ""),
            "title": data["title"],
            "date": data["date"],
            "start_time": data["start_time"],
            "duration_minutes": data.get("duration_minutes", 60),
            "status": data.get("status", "Requested"),
            "notes": data.get("notes", ""),
        }
        self._data["appointments"].append(entry)
        self._save()
        return dict(entry)

    def update_appointment(self, appointment_id, **updates):
        for i, a in enumerate(self._data["appointments"]):
            if a["appointment_id"] == appointment_id:
                self._data["appointments"][i].update(updates)
                self._save()
                return dict(self._data["appointments"][i])
        return None

    def find_appointment_conflict(self, query):
        lawyer_id = query["lawyer_id"]
        date_str = query["date"]
        start_min = _minutes_since_midnight(query["start_time"])
        end_min = start_min + query["duration_minutes"]
        exclude_id = query.get("exclude_id", "")
        for a in self._data["appointments"]:
            if a["lawyer_id"] != lawyer_id:
                continue
            if a["date"] != date_str:
                continue
            if a["status"] not in ("Approved",):
                continue
            if exclude_id and a["appointment_id"] == exclude_id:
                continue
            a_start = _minutes_since_midnight(a["start_time"])
            a_end = a_start + a["duration_minutes"]
            if start_min < a_end and end_min > a_start:
                return dict(a)
        return None

    def count_pending_appointments_for_lawyer(self, lawyer_id):
        return sum(
            1 for a in self._data["appointments"]
            if a["lawyer_id"] == lawyer_id and a["status"] == "Requested"
        )

    def upcoming_appointments_for_user(self, user_id, role, limit=5):
        key = "lawyer_id" if role == "lawyer" else "client_id"
        statuses = ("Approved", "Requested") if role == "lawyer" else ("Approved",)
        today = datetime.now().strftime("%Y-%m-%d")
        upcoming = [
            a for a in self._data["appointments"]
            if a[key] == user_id
            and a["status"] in statuses
            and a["date"] >= today
        ]
        upcoming.sort(key=lambda a: a["date"] + a.get("start_time", ""))
        return upcoming[:limit]

    def upcoming_appointments_for_lawyer(self, lawyer_id, limit=5):
        return self.upcoming_appointments_for_user(lawyer_id, "lawyer", limit)

    def upcoming_appointments_for_client(self, client_id, limit=3):
        return self.upcoming_appointments_for_user(client_id, "client", limit)

    # ── Invoice methods ──────────────────────────────────────────────────

    def get_invoices_for_lawyer(self, lawyer_id):
        return [dict(inv) for inv in self._data["invoices"] if inv["lawyer_id"] == lawyer_id]

    def get_invoices_for_client(self, client_id):
        return [dict(inv) for inv in self._data["invoices"] if inv["client_id"] == client_id]

    def get_invoice(self, invoice_id):
        for inv in self._data["invoices"]:
            if inv["invoice_id"] == invoice_id:
                return dict(inv)
        return None

    def _next_invoice_number(self):
        num = self._data["_meta"]["next_invoice_number"]
        self._data["_meta"]["next_invoice_number"] = num + 1
        self._save()
        return f"INV-{num:03d}"

    def create_invoice(self, data):
        entry = {
            "invoice_id": self._next_id("invoices", "inv"),
            "invoice_number": self._next_invoice_number(),
            "case_id": data["case_id"],
            "lawyer_id": data["lawyer_id"],
            "client_id": data["client_id"],
            "description": data["description"],
            "amount": data["amount"],
            "status": data.get("status", "Pending"),
            "due_date": data["due_date"],
            "created_at": datetime.now().isoformat(),
        }
        self._data["invoices"].append(entry)
        self._save()
        return dict(entry)

    def update_invoice(self, invoice_id, **updates):
        for i, inv in enumerate(self._data["invoices"]):
            if inv["invoice_id"] == invoice_id:
                self._data["invoices"][i].update(updates)
                self._save()
                return dict(self._data["invoices"][i])
        return None

    def count_unpaid_invoices(self):
        return sum(1 for inv in self._data["invoices"] if inv["status"] != "Paid")

    def unpaid_invoices_for_client(self, client_id):
        result = [inv for inv in self._data["invoices"]
                  if inv["client_id"] == client_id and inv["status"] != "Paid"]
        return result, sum(inv["amount"] for inv in result)

    # ── Notification methods ─────────────────────────────────────────────

    def notifications_for_user(self, user_id):
        items = [n for n in self._data["notifications"] if n["user_id"] == user_id]
        items.sort(key=lambda n: n["created_at"], reverse=True)
        return items

    def unread_notification_count(self, user_id):
        return sum(1 for n in self._data["notifications"]
                   if n["user_id"] == user_id and not n["is_read"])

    def mark_notification_read(self, notification_id):
        for n in self._data["notifications"]:
            if n["notification_id"] == notification_id:
                n["is_read"] = True
                self._save()
                return True
        return False

    def create_notification(self, notif_data):
        entry = {
            "notification_id": self._next_id("notifications", "notification"),
            "user_id": notif_data["user_id"],
            "title": notif_data["title"],
            "message": notif_data["message"],
            "notification_type": notif_data["notification_type"],
            "reference_id": notif_data.get("reference_id", ""),
            "is_read": False,
            "created_at": datetime.now().isoformat(),
        }
        self._data["notifications"].append(entry)
        self._save()
        return dict(entry)

    def mark_all_notifications_read(self, user_id):
        for n in self._data["notifications"]:
            if n["user_id"] == user_id:
                n["is_read"] = True
        self._save()

    # ── Message methods ───────────────────────────────────────────────────

    def get_messages_between(self, user_id_1, user_id_2):
        result = [
            dict(m) for m in self._data["messages"]
            if (m["sender_id"] == user_id_1 and m["receiver_id"] == user_id_2)
            or (m["sender_id"] == user_id_2 and m["receiver_id"] == user_id_1)
        ]
        result.sort(key=lambda m: m["created_at"])
        return result

    def get_messages_for_case(self, case_id, user_id):
        result = [
            dict(m) for m in self._data["messages"]
            if m["case_id"] == case_id
            and (m["sender_id"] == user_id or m["receiver_id"] == user_id)
        ]
        result.sort(key=lambda m: m["created_at"])
        return result

    def get_conversations_for_user(self, user_id):
        partners = {}
        for m in self._data["messages"]:
            if m["sender_id"] != user_id and m["receiver_id"] != user_id:
                continue
            other = m["sender_id"] if m["receiver_id"] == user_id else m["receiver_id"]
            if other not in partners or m["created_at"] > partners[other]["last_at"]:
                unread = sum(
                    1 for x in self._data["messages"]
                    if x["sender_id"] == other and x["receiver_id"] == user_id and not x["is_read"]
                )
                partners[other] = {
                    "partner_id": other,
                    "last_message": m["content"],
                    "last_at": m["created_at"],
                    "last_sender_id": m["sender_id"],
                    "case_id": m.get("case_id", ""),
                    "unread_count": unread,
                }
        result = list(partners.values())
        result.sort(key=lambda c: c["last_at"], reverse=True)
        return result

    def create_message(self, data):
        entry = {
            "message_id": self._next_id("messages", "msg"),
            "sender_id": data["sender_id"],
            "receiver_id": data["receiver_id"],
            "case_id": data.get("case_id", ""),
            "content": data["content"],
            "is_read": False,
            "created_at": datetime.now().isoformat(),
        }
        self._data["messages"].append(entry)
        self._save()
        return dict(entry)

    def mark_messages_read(self, sender_id, receiver_id):
        changed = False
        for m in self._data["messages"]:
            if m["sender_id"] == sender_id and m["receiver_id"] == receiver_id and not m["is_read"]:
                m["is_read"] = True
                changed = True
        if changed:
            self._save()

    def unread_message_count(self, user_id):
        return sum(
            1 for m in self._data["messages"]
            if m["receiver_id"] == user_id and not m["is_read"]
        )

    def get_overdue_reply_threads(self, lawyer_id):
        cutoff = (datetime.now() - timedelta(days=2)).isoformat()
        threads = {}
        for m in self._data["messages"]:
            if m["sender_id"] == lawyer_id or m["receiver_id"] == lawyer_id:
                other = m["sender_id"] if m["receiver_id"] == lawyer_id else m["receiver_id"]
                if other not in threads or m["created_at"] > threads[other]["last_at"]:
                    threads[other] = {
                        "partner_id": other,
                        "last_sender_id": m["sender_id"],
                        "last_at": m["created_at"],
                    }
        overdue = []
        for partner_id, info in threads.items():
            if info["last_sender_id"] != lawyer_id and info["last_at"] < cutoff:
                client = self.get_user(partner_id)
                client_name = f"{client['first_name']} {client['last_name']}" if client else "Unknown"
                overdue.append({
                    "partner_id": partner_id,
                    "client_name": client_name,
                    "last_at": info["last_at"],
                })
        return overdue

    # ── Case file methods ────────────────────────────────────────────────

    def get_files_for_case(self, case_id, viewer_user_id, viewer_role):
        all_files = [dict(f) for f in self._data.get("case_files", [])
                     if f["case_id"] == case_id]
        if viewer_role == "lawyer":
            return all_files
        return [
            f for f in all_files
            if f["added_by"] == viewer_user_id or f["shared_with_client"]
        ]

    def add_case_file(self, data):
        entry = {
            "file_id": self._next_id("case_files", "file"),
            "case_id": data["case_id"],
            "added_by": data["added_by"],
            "file_name": data["file_name"],
            "file_path": data["file_path"],
            "shared_with_client": data.get("shared_with_client", False),
            "added_at": datetime.now().isoformat(),
        }
        self._data.setdefault("case_files", []).append(entry)
        self._save()
        return dict(entry)

    def toggle_file_sharing(self, file_id):
        for f in self._data.get("case_files", []):
            if f["file_id"] == file_id:
                f["shared_with_client"] = not f["shared_with_client"]
                self._save()
                return dict(f)
        return None

    def delete_case_file(self, file_id):
        for i, f in enumerate(self._data.get("case_files", [])):
            if f["file_id"] == file_id:
                del self._data["case_files"][i]
                self._save()
                return True
        return False

    # ── Law book methods ──────────────────────────────────────────────────

    def get_all_law_books(self):
        return [dict(b) for b in self._data.get("law_books", [])]

    def get_law_book(self, book_id):
        for b in self._data.get("law_books", []):
            if b["book_id"] == book_id:
                return dict(b)
        return None

    def create_law_book(self, data):
        entry = {
            "book_id": self._next_id("law_books", "book"),
            "title": data["title"],
            "author": data.get("author", ""),
            "edition": data.get("edition", ""),
            "isbn": data.get("isbn", ""),
            "category": data.get("category", ""),
            "file_name": data["file_name"],
            "added_by": data["added_by"],
            "added_at": datetime.now().isoformat(),
        }
        self._data.setdefault("law_books", []).append(entry)
        self._save()
        return dict(entry)

    def delete_law_book(self, book_id):
        for coll in ("book_comments", "book_chats"):
            self._data[coll] = [item for item in self._data.get(coll, []) if item.get("book_id") != book_id]
        for i, b in enumerate(self._data.get("law_books", [])):
            if b["book_id"] == book_id:
                del self._data["law_books"][i]
                self._save()
                return True
        return False

    def get_book_comments(self, book_id):
        result = [dict(c) for c in self._data.get("book_comments", [])
                  if c["book_id"] == book_id]
        result.sort(key=lambda c: c.get("page_number", 0))
        return result

    def create_book_comment(self, data):
        entry = {
            "comment_id": self._next_id("book_comments", "bcomment"),
            "book_id": data["book_id"],
            "user_id": data["user_id"],
            "title": data["title"],
            "page_number": data.get("page_number", 0),
            "content": data["content"],
            "created_at": datetime.now().isoformat(),
        }
        self._data.setdefault("book_comments", []).append(entry)
        self._save()
        return dict(entry)

    def get_book_chats(self, book_id):
        result = [dict(m) for m in self._data.get("book_chats", [])
                  if m["book_id"] == book_id]
        result.sort(key=lambda m: m["created_at"])
        return result

    def create_book_chat(self, data):
        entry = {
            "chat_id": self._next_id("book_chats", "bchat"),
            "book_id": data["book_id"],
            "user_id": data["user_id"],
            "content": data["content"],
            "created_at": datetime.now().isoformat(),
        }
        self._data.setdefault("book_chats", []).append(entry)
        self._save()
        return dict(entry)

    # ── Stakeholder / analytics methods ───────────────────────────────────

    def get_all_cases(self):
        return [dict(c) for c in self._data["cases"]]

    def get_all_invoices(self):
        return [dict(inv) for inv in self._data["invoices"]]

    def get_all_appointments(self):
        return [dict(a) for a in self._data["appointments"]]

    def get_user_preferences(self, user_id):
        user = self.get_user(user_id)
        if user and "dashboard_preferences" in user:
            return dict(user["dashboard_preferences"])
        return None

    def update_user_preferences(self, user_id, preferences):
        for i, u in enumerate(self._data["users"]):
            if u["user_id"] == user_id:
                self._data["users"][i]["dashboard_preferences"] = preferences
                self._save()
                return True
        return False


# ── Seed Data ─────────────────────────────────────────────────────────────

def _build_seed_data():
    now = datetime.now().isoformat()
    users = [
        {"user_id": "user_1", "username": "sarah.jenkins", "password": "lawyer123", "role": "lawyer",
         "first_name": "Sarah", "last_name": "Jenkins", "email": "sarah@engaz.com", "phone": "555-0101"},
        {"user_id": "user_2", "username": "david.miller", "password": "lawyer123", "role": "lawyer",
         "first_name": "David", "last_name": "Miller", "email": "david@engaz.com", "phone": "555-0102"},
        {"user_id": "user_3", "username": "maria.garcia", "password": "lawyer123", "role": "lawyer",
         "first_name": "Maria", "last_name": "Garcia", "email": "maria@engaz.com", "phone": "555-0103"},
        {"user_id": "user_4", "username": "john.doe", "password": "client123", "role": "client",
         "first_name": "John", "last_name": "Doe", "email": "john@email.com", "phone": "555-0201"},
        {"user_id": "user_5", "username": "jane.smith", "password": "client123", "role": "client",
         "first_name": "Jane", "last_name": "Smith", "email": "jane@email.com", "phone": "555-0202"},
        {"user_id": "user_6", "username": "mike.johnson", "password": "client123", "role": "client",
         "first_name": "Mike", "last_name": "Johnson", "email": "mike@email.com", "phone": "555-0203"},
        {"user_id": "user_7", "username": "lisa.wong", "password": "client123", "role": "client",
         "first_name": "Lisa", "last_name": "Wong", "email": "lisa@email.com", "phone": "555-0204"},
        {"user_id": "user_8", "username": "ahmad.al-rashid", "password": "stakeholder123", "role": "stakeholder",
         "first_name": "Ahmad", "last_name": "Al-Rashid", "email": "ahmad@engaz.com", "phone": "0501234567",
         "dashboard_preferences": {
             "visible_metrics": ["closing_rate", "revenue", "cases_by_status", "cases_by_department",
                                  "top_lawyers_closing", "top_lawyers_revenue", "workload",
                                  "appointments", "client_trends"],
             "layout_order": ["closing_rate", "revenue", "cases_by_status", "cases_by_department",
                              "top_lawyers_closing", "top_lawyers_revenue", "workload",
                              "appointments", "client_trends"],
         }},
    ]
    cases = [
        {"case_id": "case_1", "case_number": "CASE-001", "title": "Smith vs. State",
         "description": "Criminal defense case regarding alleged theft.", "case_type": "criminal",
         "status": "Open", "client_id": "user_4", "lawyer_id": "user_1", "created_at": now},
        {"case_id": "case_2", "case_number": "CASE-002", "title": "Parker Estate Planning",
         "description": "Civil case for estate distribution.", "case_type": "civil",
         "status": "In Progress", "client_id": "user_5", "lawyer_id": "user_2", "created_at": now},
        {"case_id": "case_3", "case_number": "CASE-003", "title": "TechCorp Incorporation",
         "description": "Corporate registration and compliance.", "case_type": "corporate",
         "status": "Open", "client_id": "user_6", "lawyer_id": "user_3", "created_at": now},
        {"case_id": "case_4", "case_number": "CASE-004", "title": "Wong Custody Agreement",
         "description": "Family law custody arrangement.", "case_type": "family",
         "status": "Closed", "client_id": "user_7", "lawyer_id": "user_1", "created_at": now},
        {"case_id": "case_5", "case_number": "CASE-005", "title": "Doe Property Dispute",
         "description": "Civil dispute over property boundaries.", "case_type": "civil",
         "status": "In Progress", "client_id": "user_4", "lawyer_id": "user_3", "created_at": now},
        {"case_id": "case_6", "case_number": "CASE-006", "title": "Smith Misdemeanor Appeal",
         "description": "Appeal for misdemeanor conviction.", "case_type": "criminal",
         "status": "Open", "client_id": "user_5", "lawyer_id": "user_1", "created_at": now},
    ]
    appointments = [
        {"appointment_id": "app_1", "client_id": "user_4", "lawyer_id": "user_1", "case_id": "case_1",
         "title": "Initial Consultation", "date": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
         "start_time": "10:00", "duration_minutes": 60, "status": "Approved", "notes": "First meeting."},
        {"appointment_id": "app_2", "client_id": "user_5", "lawyer_id": "user_2", "case_id": "case_2",
         "title": "Estate Review", "date": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
         "start_time": "14:00", "duration_minutes": 45, "status": "Approved", "notes": "Document review."},
        {"appointment_id": "app_3", "client_id": "user_6", "lawyer_id": "user_3", "case_id": "case_3",
         "title": "Compliance Check", "date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
         "start_time": "09:00", "duration_minutes": 30, "status": "Completed", "notes": "Annual check."},
        {"appointment_id": "app_4", "client_id": "user_7", "lawyer_id": "user_1", "case_id": "case_4",
         "title": "Custody Mediation", "date": (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d"),
         "start_time": "11:00", "duration_minutes": 90, "status": "Requested", "notes": "Mediation session."},
        {"appointment_id": "app_5", "client_id": "user_4", "lawyer_id": "user_2", "case_id": "",
         "title": "Property Inspection", "date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
         "start_time": "08:30", "duration_minutes": 120, "status": "Requested", "notes": "On-site visit."},
    ]
    invoices = [
        {"invoice_id": "inv_1", "invoice_number": "INV-001", "case_id": "case_1", "lawyer_id": "user_1",
         "client_id": "user_4", "description": "Retainer for criminal defense", "amount": 2500.00,
         "status": "Pending", "due_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
         "created_at": now},
        {"invoice_id": "inv_2", "invoice_number": "INV-002", "case_id": "case_2", "lawyer_id": "user_2",
         "client_id": "user_5", "description": "Estate planning consultation", "amount": 1500.00,
         "status": "Paid", "due_date": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
         "created_at": now},
        {"invoice_id": "inv_3", "invoice_number": "INV-003", "case_id": "case_3", "lawyer_id": "user_3",
         "client_id": "user_6", "description": "Corporate filing fees", "amount": 3200.00,
         "status": "Overdue", "due_date": (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"),
         "created_at": now},
        {"invoice_id": "inv_4", "invoice_number": "INV-004", "case_id": "case_4", "lawyer_id": "user_1",
         "client_id": "user_7", "description": "Custody case retainer", "amount": 1800.00,
         "status": "Pending", "due_date": (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d"),
         "created_at": now},
    ]
    notifications = [
        {"notification_id": "notif_1", "user_id": "user_1", "title": "New Appointment Request",
         "message": "Lisa Wong requested a custody mediation.", "notification_type": "appointment_requested",
         "reference_id": "app_4", "is_read": False, "created_at": now},
        {"notification_id": "notif_2", "user_id": "user_4", "title": "Invoice Created",
         "message": "A new invoice (INV-001) has been created for your case.", "notification_type": "invoice_created",
         "reference_id": "inv_1", "is_read": False, "created_at": now},
        {"notification_id": "notif_3", "user_id": "user_5", "title": "Appointment Approved",
         "message": "Your estate review has been approved.", "notification_type": "appointment_approved",
         "reference_id": "app_2", "is_read": True, "created_at": now},
        {"notification_id": "notif_4", "user_id": "user_6", "title": "Invoice Overdue",
         "message": "Invoice INV-003 is now overdue.", "notification_type": "invoice_created",
         "reference_id": "inv_3", "is_read": False, "created_at": now},
        {"notification_id": "notif_5", "user_id": "user_1", "title": "New Appointment Request",
         "message": "John Doe requested a property inspection.", "notification_type": "appointment_requested",
         "reference_id": "app_5", "is_read": False, "created_at": now},
        {"notification_id": "notif_6", "user_id": "user_2", "title": "Invoice Paid",
         "message": "Jane Smith paid invoice INV-002.", "notification_type": "invoice_paid",
         "reference_id": "inv_2", "is_read": True, "created_at": now},
    ]
    meta = {"next_case_number": 7, "next_invoice_number": 5}
    return {
        "_meta": meta, "users": users, "cases": cases, "appointments": appointments,
        "invoices": invoices, "messages": [], "notifications": notifications,
        "case_files": [],
        "law_books": [],
        "book_comments": [],
        "book_chats": [],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Reusable UI Components
# ═══════════════════════════════════════════════════════════════════════════

class _ErrorLabel(QLabel):
    """Small red error message label, hidden by default."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"color: {RED}; font-size: 11px; margin-left: 4px;")
        self.hide()

    def show_message(self, text):
        self.setText(text)
        self.show()

    def clear_message(self):
        self.setText("")
        self.hide()


class StatCard(QFrame):
    """Reusable dashboard stat card."""

    clicked = Signal()

    def __init__(self, title, value, color=TEXT_DARK, parent=None):
        super().__init__(parent)
        self.setFixedHeight(110)
        self.setMinimumWidth(180)
        self.setStyleSheet(f"""
            StatCard {{ background-color: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 10px; }}
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 13px; border: none; background: transparent;")
        self.title_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.value_lbl = QLabel(str(value))
        self.value_lbl.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold; border: none; background: transparent;")
        self.value_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.title_lbl)
        layout.addStretch()
        layout.addWidget(self.value_lbl)
        self._hover = False
        self._card_bg = CARD_BG

    def mousePressEvent(self, event):
        self.clicked.emit()

    def enterEvent(self, event):
        self._hover = True
        self.setStyleSheet(f"StatCard {{ background-color: #F8FAFC; border: 2px solid {STEEL}; border-radius: 10px; }}")

    def leaveEvent(self, event):
        self._hover = False
        self.setStyleSheet(f"StatCard {{ background-color: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 10px; }}")

    def set_value(self, value):
        self.value_lbl.setText(str(value))


# ═══════════════════════════════════════════════════════════════════════════
# Login Screen
# ═══════════════════════════════════════════════════════════════════════════

class LoginScreen(QWidget):
    login_successful = Signal(dict)

    def __init__(self, repo):
        super().__init__()
        self._repo = repo
        self.setWindowTitle("Engaz — Login")
        self.resize(460, 400)
        self.setMinimumSize(400, 340)
        self._setup_ui()
        self._center_on_screen()

    def _setup_ui(self):
        self.setStyleSheet(f"background: {LIGHT_GRAY};")
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setStyleSheet(f"QFrame {{ background: {WHITE}; border-radius: 10px; border: 1px solid {BORDER}; }}")
        card.setMinimumSize(360, 260)
        card.setMaximumWidth(400)
        outer.addWidget(card, alignment=Qt.AlignCenter)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 28, 32, 20)
        layout.setSpacing(10)

        welcome = QLabel("Welcome to Engaz")
        welcome.setAlignment(Qt.AlignCenter)
        welcome.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {NAVY}; border: none;")
        layout.addWidget(welcome)

        subtitle = QLabel("Sign in to access your dashboard")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"font-size: 12px; color: {TEXT_GRAY}; border: none;")
        layout.addWidget(subtitle)
        layout.addSpacing(12)

        username_label = QLabel("Username")
        username_label.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {TEXT_DARK}; border: none;")
        asterisk1 = QLabel("*")
        asterisk1.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {RED}; border: none;")
        username_row = QHBoxLayout()
        username_row.setSpacing(2)
        username_row.addWidget(username_label)
        username_row.addWidget(asterisk1)
        username_row.addStretch()
        layout.addLayout(username_row)

        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText("Enter username")
        self._username_input.setStyleSheet(self._input_style())
        self._username_input.returnPressed.connect(self._move_to_password)
        layout.addWidget(self._username_input)

        self._username_error = _ErrorLabel()
        layout.addWidget(self._username_error)

        password_label = QLabel("Password")
        password_label.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {TEXT_DARK}; border: none;")
        asterisk2 = QLabel("*")
        asterisk2.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {RED}; border: none;")
        password_row = QHBoxLayout()
        password_row.setSpacing(2)
        password_row.addWidget(password_label)
        password_row.addWidget(asterisk2)
        password_row.addStretch()
        layout.addLayout(password_row)

        self._password_input = QLineEdit()
        self._password_input.setPlaceholderText("Enter password")
        self._password_input.setEchoMode(QLineEdit.Password)
        self._password_input.setStyleSheet(self._input_style())
        self._password_input.returnPressed.connect(self._attempt_login)
        layout.addWidget(self._password_input)

        self._password_error = _ErrorLabel()
        layout.addWidget(self._password_error)

        layout.addSpacing(8)

        self._login_error = _ErrorLabel()
        layout.addWidget(self._login_error)

        login_btn = QPushButton("Sign In")
        login_btn.setStyleSheet(f"""
            QPushButton {{ background: {NAVY}; color: {WHITE}; border: none; border-radius: 6px;
                           padding: 10px; font-size: 14px; font-weight: bold; }}
            QPushButton:hover {{ background: {STEEL}; }}
        """)
        login_btn.clicked.connect(self._attempt_login)
        layout.addWidget(login_btn)

    def _input_style(self):
        return f"""
            QLineEdit {{ padding: 8px; border: 1px solid {BORDER}; border-radius: 4px;
                         font-size: 13px; color: {TEXT_DARK}; background: {WHITE}; }}
            QLineEdit:focus {{ border-color: {STEEL}; }}
        """

    def _move_to_password(self):
        self._password_input.setFocus()

    def _attempt_login(self):
        self._clear_errors()
        username = self._username_input.text().strip()
        password = self._password_input.text().strip()
        if not username and not password:
            self._username_error.show_message("Username is required")
            self._password_error.show_message("Password is required")
            return
        if not username:
            self._username_error.show_message("Username is required")
            return
        if not password:
            self._password_error.show_message("Password is required")
            return
        user = self._repo.find_user_by_credentials(username, password)
        if user is None:
            self._login_error.show_message("Invalid username or password")
            return
        self.login_successful.emit(user)

    def _clear_errors(self):
        self._username_error.clear_message()
        self._password_error.clear_message()
        self._login_error.clear_message()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())


# ═══════════════════════════════════════════════════════════════════════════
# Sidebar
# ═══════════════════════════════════════════════════════════════════════════

class Sidebar(QFrame):
    page_selected = Signal(int)
    reset_requested = Signal()

    MENUS = {
        "lawyer": [
            ("🏠  Main Menu", "🏠", PAGE_DASHBOARD),
            ("📜  Cases", "📜", PAGE_CASES),
            ("🗓️  Calendar", "🗓️", PAGE_CALENDAR),
            ("🧾  Invoices", "🧾", PAGE_INVOICES),
            ("💬  Messages", "💬", PAGE_MESSAGES),
            ("📈  Reports", "📈", PAGE_REPORTS),
            ("📖  References", "📖", PAGE_LAW_LIBRARY),
        ],
        "client": [
            ("🏠  Main Menu", "🏠", PAGE_DASHBOARD),
            ("📜  My Cases", "📜", PAGE_CASES),
            ("🗓️  Appointments", "🗓️", PAGE_CALENDAR),
            ("🧾  Invoices", "🧾", PAGE_INVOICES),
            ("💬  Messages", "💬", PAGE_MESSAGES),
        ],
        "stakeholder": [
            ("📈  Dashboard", "📈", PAGE_STAKEHOLDER_DASHBOARD),
        ],
    }

    def __init__(self, role):
        super().__init__()
        self._role = role
        self._expanded = True
        self._expanded_width = 210
        self._collapsed_width = 54
        self._buttons = []
        self._labels = []
        self._icon_texts = []
        self._active_index = 0
        self.setFixedWidth(self._expanded_width)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"background: {NAVY}; border: none;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(2)

        layout.addSpacing(4)

        for idx, (label, icon, page) in enumerate(self.MENUS[self._role]):
            btn = QPushButton(label)
            btn.setFixedHeight(42)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, p=page, i=idx: self._select_page(p, i))
            self._buttons.append(btn)
            self._icon_texts.append((icon, label))
            layout.addWidget(btn)

        layout.addStretch()

        if self._role == "lawyer":
            layout.addWidget(self._make_bottom_button("🔄  Reset Data", "🔄", self._confirm_reset))

        layout.addWidget(self._make_bottom_button("🚪  Logout", "🚪", lambda: self.page_selected.emit(-1)))
        layout.addSpacing(4)
        self._update_button_styles()

    def _make_bottom_button(self, full_text, icon_text, callback):
        btn = QPushButton(full_text)
        btn.setFixedHeight(40)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(self._btn_style(active=False))
        btn.clicked.connect(callback)
        self._icon_texts.append((icon_text, full_text))
        self._buttons.append(btn)
        return btn

    def _btn_style(self, active, collapsed=False):
        align = "center" if collapsed else "left"
        pad = "0px" if collapsed else "14px"
        if active:
            return f"""
                QPushButton {{ background: {STEEL}; color: {WHITE}; border: none;
                               text-align: {align}; padding-left: {pad}; font-size: 13px; border-radius: 0px;
                               border-left: 3px solid {WHITE}; }}
            """
        return f"""
            QPushButton {{ background: {NAVY}; color: {WHITE}; border: none;
                           text-align: {align}; padding-left: {pad}; font-size: 13px; border-radius: 0px; }}
            QPushButton:hover {{ background: rgba(255, 255, 255, 0.1); }}
        """

    def toggle(self):
        self._expanded = not self._expanded
        self.setFixedWidth(self._expanded_width if self._expanded else self._collapsed_width)
        for i, btn in enumerate(self._buttons):
            if not self._expanded:
                btn.setText(self._icon_texts[i][0])
            else:
                btn.setText(self._icon_texts[i][1])
        self._update_button_styles()

    def _select_page(self, page, index):
        self._active_index = index
        self._update_button_styles()
        self.page_selected.emit(page)

    def _update_button_styles(self):
        for i, btn in enumerate(self._buttons):
            btn.setStyleSheet(self._btn_style(active=(i == self._active_index), collapsed=not self._expanded))

    def _confirm_reset(self):
        answer = QMessageBox.warning(
            self, "Reset to Defaults",
            "This will delete all data and restore factory defaults.\n\nAre you sure?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.reset_requested.emit()


# ═══════════════════════════════════════════════════════════════════════════
# Header Bar & Notification Dropdown
# ═══════════════════════════════════════════════════════════════════════════

class _NotificationItem(QFrame):
    """Clickable notification row inside the dropdown."""

    def __init__(self, notif, on_click, parent=None):
        super().__init__(parent)
        self._notif = notif
        self._on_click = on_click
        self.setCursor(Qt.PointingHandCursor)
        self._build()

    def _build(self):
        bg = LIGHT_GRAY if not self._notif["is_read"] else WHITE
        self.setStyleSheet(f"""
            background: {bg}; padding: 4px; border: none; border-bottom: 1px solid {BORDER};
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(0)
        title = QLabel(self._notif["title"])
        title.setStyleSheet(f"font-weight: bold; color: {TEXT_DARK}; font-size: 12px; border: none;")
        msg = QLabel(self._notif["message"])
        msg.setWordWrap(True)
        msg.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 11px; border: none;")
        layout.addWidget(title)
        layout.addWidget(msg)

    def mousePressEvent(self, event):
        self._on_click(self._notif)
        super().mousePressEvent(event)


class NotificationDropdown(QFrame):
    notification_clicked = Signal(dict)
    badge_refresh_requested = Signal()

    def __init__(self, repo, user_id, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self._repo = repo
        self._user_id = user_id
        self.setFixedWidth(330)
        self.setMaximumHeight(400)
        self.setStyleSheet(f"background: {WHITE}; border: 1px solid {BORDER}; border-radius: 4px;")
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header_row = QWidget()
        header_row.setFixedHeight(36)
        header_row.setStyleSheet(f"background: {LIGHT_GRAY}; border: none; border-radius: 0px;")
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(8, 0, 8, 0)
        header_title = QLabel("Notifications")
        header_title.setStyleSheet(f"font-weight: bold; color: {TEXT_DARK}; font-size: 13px; border: none;")
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        mark_all = QLabel("Mark all as read")
        mark_all.setCursor(Qt.PointingHandCursor)
        mark_all.setStyleSheet(f"color: {NAVY}; font-size: 11px; border: none; text-decoration: underline;")
        mark_all.mousePressEvent = lambda e: self._mark_all_read()
        header_layout.addWidget(mark_all)
        root.addWidget(header_row)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"border: none; background: {WHITE};")
        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        scroll.setWidget(self._list_widget)
        root.addWidget(scroll)

    def refresh(self):
        clear_layout(self._list_layout)
        items = self._repo.notifications_for_user(self._user_id)
        if not items:
            empty = QLabel("  No notifications")
            empty.setStyleSheet(f"color: {TEXT_GRAY}; padding: 16px; border: none;")
            self._list_layout.insertWidget(0, empty)
        else:
            for notif in items:
                row = _NotificationItem(notif, self._on_item_clicked)
                self._list_layout.insertWidget(self._list_layout.count() - 1, row)
        self._list_layout.addStretch()

    def _on_item_clicked(self, notif):
        self._repo.mark_notification_read(notif["notification_id"])
        self.notification_clicked.emit(notif)
        self.hide()

    def _mark_all_read(self):
        self._repo.mark_all_notifications_read(self._user_id)
        self.badge_refresh_requested.emit()
        self.refresh()


class HeaderBar(QFrame):
    notification_clicked = Signal(str, dict)
    sidebar_toggle_requested = Signal()

    def __init__(self, repo, user, navigate_callback, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._user = user
        self._navigate = navigate_callback
        self._dropdown = None
        self.setFixedHeight(54)
        self._build()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE}; border-bottom: 1px solid {BORDER};")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)

        hamburger = QPushButton("☰")
        hamburger.setFixedSize(36, 36)
        hamburger.setCursor(Qt.PointingHandCursor)
        hamburger.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {NAVY}; border: none;
                           font-size: 18px; border-radius: 4px; }}
            QPushButton:hover {{ background: {LIGHT_GRAY}; }}
        """)
        hamburger.clicked.connect(self.sidebar_toggle_requested.emit)
        layout.addWidget(hamburger)

        brand = QLabel("Engaz")
        brand.setStyleSheet(f"font-size: 17px; font-weight: bold; color: {NAVY}; border: none; margin-left: 6px;")
        layout.addWidget(brand)
        layout.addStretch()

        role = self._user["role"].capitalize()
        info = QLabel(f"{self._user['first_name']} {self._user['last_name']}  |  {role}")
        info.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 12px; border: none; margin-right: 4px;")
        layout.addWidget(info)

        self._bell_btn = QPushButton()
        self._bell_btn.setFixedSize(36, 36)
        self._bell_btn.setCursor(Qt.PointingHandCursor)
        self._bell_btn.setStyleSheet(f"""
            QPushButton {{ background: {LIGHT_GRAY}; border: none; border-radius: 18px; font-size: 18px; padding: 0px; }}
            QPushButton:hover {{ background: {BORDER}; }}
        """)
        self._bell_btn.setText("🔔")
        self._bell_btn.clicked.connect(self._toggle_notifications)
        layout.addWidget(self._bell_btn)

        self._badge = QLabel("0", self._bell_btn)
        self._badge.setAlignment(Qt.AlignCenter)
        self._badge.setFixedSize(18, 18)
        self._badge.setStyleSheet(f"background: {RED}; color: {WHITE}; font-size: 10px;"
                                  f" font-weight: bold; border-radius: 9px; border: none;")
        self._badge.move(22, 0)
        self._badge.hide()

        self.refresh_badge()

    def refresh_badge(self):
        count = self._repo.unread_notification_count(self._user["user_id"])
        if count > 0:
            self._badge.setText(str(count))
            self._badge.show()
        else:
            self._badge.hide()

    def _toggle_notifications(self):
        if self._dropdown and self._dropdown.isVisible():
            self._dropdown.hide()
            return
        self._show_dropdown()

    def _show_dropdown(self):
        if self._dropdown is None:
            self._dropdown = NotificationDropdown(self._repo, self._user["user_id"])
            self._dropdown.notification_clicked.connect(self._on_notification_item_clicked)
            self._dropdown.badge_refresh_requested.connect(self.refresh_badge)
        self._dropdown.refresh()
        self._dropdown.adjustSize()
        pos = self._bell_btn.mapToGlobal(QPoint(0, self._bell_btn.height()))
        dw = self._dropdown.width()
        self._dropdown.move(pos.x() + self._bell_btn.width() - dw, pos.y())
        self._dropdown.show()

    def _on_notification_item_clicked(self, notif):
        self.refresh_badge()
        page = NOTIFICATION_PAGE.get(notif["notification_type"], PAGE_DASHBOARD)
        self._navigate(page)
        self.notification_clicked.emit(notif["notification_type"], notif)


# ═══════════════════════════════════════════════════════════════════════════
# Dashboard Page
# ═══════════════════════════════════════════════════════════════════════════

class DashboardPage(QWidget):
    appointment_clicked = Signal(str)

    def __init__(self, repo, user, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._user = user
        self._stat_cards = []
        self._appointments_container = None
        self._appointments_layout = None
        self._build()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 28, 28, 28)

        heading = QLabel(f"Welcome back, {self._user['first_name']}")
        heading.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        content_layout.addWidget(heading)
        content_layout.addSpacing(20)

        self._stat_cards = []

        if self._user["role"] == "lawyer":
            self._build_lawyer_dashboard(content_layout)
        else:
            self._build_client_dashboard(content_layout)

        content_layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def refresh(self):
        uid = self._user["user_id"]
        if self._user["role"] == "lawyer":
            vals = [
                self._repo.count_active_cases_for_lawyer(uid),
                self._repo.count_pending_appointments_for_lawyer(uid),
                self._repo.count_unpaid_invoices(),
                self._repo.unread_notification_count(uid),
            ]
        else:
            unpaid_list, total_unpaid = self._repo.unpaid_invoices_for_client(uid)
            vals = [
                self._repo.count_active_cases_for_client(uid),
                f"{len(unpaid_list)} (${total_unpaid:,.2f})",
                self._repo.unread_notification_count(uid),
            ]
        for card, val in zip(self._stat_cards, vals):
            card.set_value(val)

        if self._appointments_container is not None:
            self._refresh_appointments_section()

    def _refresh_appointments_section(self):
        clear_layout(self._appointments_layout)
        uid = self._user["user_id"]
        if self._user["role"] == "lawyer":
            appts = self._repo.upcoming_appointments_for_lawyer(uid)
        else:
            appts = self._repo.upcoming_appointments_for_client(uid)
        if not appts:
            empty = QLabel("No upcoming appointments")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 13px; padding: 20px; border: none;")
            self._appointments_layout.addWidget(empty)
        else:
            for appt in appts:
                self._appointments_layout.addWidget(self._make_appointment_card(appt))

    def _build_lawyer_dashboard(self, outer):
        uid = self._user["user_id"]
        cards = QHBoxLayout()
        cards.setSpacing(16)
        c1 = StatCard("Active Cases", self._repo.count_active_cases_for_lawyer(uid))
        c2 = StatCard("Pending Appointments", self._repo.count_pending_appointments_for_lawyer(uid))
        c2.setCursor(Qt.PointingHandCursor)
        c2.clicked.connect(lambda: self.appointment_clicked.emit(datetime.now().strftime("%Y-%m-%d")))
        c3 = StatCard("Pending Invoices", self._repo.count_unpaid_invoices(), AMBER)
        c4 = StatCard("Unread Notifications", self._repo.unread_notification_count(uid), RED)
        self._stat_cards = [c1, c2, c3, c4]
        cards.addWidget(c1)
        cards.addWidget(c2)
        cards.addWidget(c3)
        cards.addWidget(c4)
        cards.addStretch()
        outer.addLayout(cards)
        outer.addSpacing(24)

        upcoming_label = QLabel("Upcoming Appointments")
        upcoming_label.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        outer.addWidget(upcoming_label)
        outer.addSpacing(8)

        self._appointments_container = QWidget()
        self._appointments_layout = QVBoxLayout(self._appointments_container)
        self._appointments_layout.setContentsMargins(0, 0, 0, 0)
        self._appointments_layout.setSpacing(6)
        self._refresh_appointments_section()
        outer.addWidget(self._appointments_container)

    def _build_client_dashboard(self, outer):
        uid = self._user["user_id"]
        cards = QHBoxLayout()
        cards.setSpacing(16)
        c1 = StatCard("My Cases", self._repo.count_active_cases_for_client(uid))
        unpaid_list, total_unpaid = self._repo.unpaid_invoices_for_client(uid)
        c2 = StatCard("Unpaid Invoices", f"{len(unpaid_list)} (${total_unpaid:,.2f})", AMBER)
        c3 = StatCard("Unread Notifications", self._repo.unread_notification_count(uid), RED)
        self._stat_cards = [c1, c2, c3]
        cards.addWidget(c1)
        cards.addWidget(c2)
        cards.addWidget(c3)
        cards.addStretch()
        outer.addLayout(cards)
        outer.addSpacing(24)

        upcoming_label = QLabel("Upcoming Appointments")
        upcoming_label.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        outer.addWidget(upcoming_label)
        outer.addSpacing(8)

        self._appointments_container = QWidget()
        self._appointments_layout = QVBoxLayout(self._appointments_container)
        self._appointments_layout.setContentsMargins(0, 0, 0, 0)
        self._appointments_layout.setSpacing(6)
        self._refresh_appointments_section()
        outer.addWidget(self._appointments_container)

    def _make_appointment_card(self, appt):
        frame = QFrame()
        frame.setCursor(Qt.PointingHandCursor)
        frame.setProperty("appt_date", appt["date"])
        frame.setProperty("hover", False)
        frame.installEventFilter(self)
        frame.setStyleSheet(f"background-color: {CARD_BG}; border: 1px solid {BORDER};"
                            f" border-radius: 8px; padding: 10px; margin-bottom: 4px;")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 30))
        frame.setGraphicsEffect(shadow)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)
        info = QVBoxLayout()
        title = QLabel(appt["title"])
        title.setStyleSheet(f"font-weight: bold; color: {TEXT_DARK}; font-size: 13px; border: none; background: transparent;")
        title.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        date_str = f"{appt['date']}  {appt.get('start_time', '')}  ({appt.get('duration_minutes', 0)} min)"
        detail = QLabel(date_str)
        detail.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 12px; border: none; background: transparent;")
        detail.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        info.addWidget(title)
        info.addWidget(detail)
        layout.addLayout(info)
        layout.addStretch()
        badge = _status_badge(appt.get("status", ""))
        badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(badge)
        return frame

    def eventFilter(self, obj, event):
        if isinstance(obj, QFrame) and obj.property("appt_date"):
            if event.type() == QEvent.Type.Enter:
                obj.setProperty("hover", True)
                obj.setStyleSheet(f"background-color: #F8FAFC; border: 2px solid {STEEL};"
                                  f" border-radius: 8px; padding: 9px; margin-bottom: 4px;")
                return True
            elif event.type() == QEvent.Type.Leave:
                obj.setProperty("hover", False)
                obj.setStyleSheet(f"background-color: {CARD_BG}; border: 1px solid {BORDER};"
                                  f" border-radius: 8px; padding: 10px; margin-bottom: 4px;")
                return True
            elif event.type() == QEvent.Type.MouseButtonPress:
                date_str = obj.property("appt_date")
                if date_str:
                    self.appointment_clicked.emit(date_str)
                return True
        return super().eventFilter(obj, event)


# ═══════════════════════════════════════════════════════════════════════════
# Case Management
# ═══════════════════════════════════════════════════════════════════════════

class CaseForm(QDialog):
    def __init__(self, repo, case=None, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._case = case
        self._is_edit = case is not None
        self._case_deleted = False
        self.setWindowTitle("Edit Case" if self._is_edit else "New Case")
        self.resize(520, 460)
        self.setMinimumSize(440, 380)
        self._build()
        if self._is_edit:
            self._fill_form()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.setVerticalSpacing(8)
        grid.setHorizontalSpacing(12)
        grid.setColumnStretch(1, 1)

        r = 0
        grid.addWidget(self._required_label("Title"), r, 0)
        self._title_input = QLineEdit()
        self._title_input.setStyleSheet(self._field_style())
        grid.addWidget(self._title_input, r, 1)
        self._title_error = _ErrorLabel()
        grid.addWidget(self._title_error, r, 2)
        r += 1

        label = self._label("Description")
        label.setAlignment(Qt.AlignRight | Qt.AlignTop)
        grid.addWidget(label, r, 0)
        self._desc_input = QTextEdit()
        self._desc_input.setMaximumHeight(80)
        self._desc_input.setStyleSheet(self._field_style())
        self._desc_input.setPlainText("")
        grid.addWidget(self._desc_input, r, 1)
        r += 1

        grid.addWidget(self._required_label("Case Type"), r, 0)
        self._type_input = ArrowComboBox()
        self._type_input.addItems(["criminal", "civil", "corporate", "family"])
        self._type_input.setStyleSheet(self._field_style())
        self._type_input.setEditable(False)
        self._type_input.setView(QListView())
        self._type_input.setInsertPolicy(QComboBox.NoInsert)
        grid.addWidget(self._type_input, r, 1)
        self._type_error = _ErrorLabel()
        grid.addWidget(self._type_error, r, 2)
        r += 1

        grid.addWidget(self._required_label("Client"), r, 0)
        self._client_input = ArrowComboBox()
        for client in self._repo.get_all_clients():
            self._client_input.addItem(
                f"{client['first_name']} {client['last_name']}", client["user_id"]
            )
        self._client_input.setStyleSheet(self._field_style())
        self._client_input.setEditable(False)
        self._client_input.setView(QListView())
        self._client_input.setInsertPolicy(QComboBox.NoInsert)
        grid.addWidget(self._client_input, r, 1)
        self._client_error = _ErrorLabel()
        grid.addWidget(self._client_error, r, 2)
        r += 1

        label = self._label("Status")
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(label, r, 0)
        self._status_input = ArrowComboBox()
        self._status_input.addItems(["Open", "In Progress", "Closed"])
        self._status_input.setStyleSheet(self._field_style())
        self._status_input.setEditable(False)
        self._status_input.setView(QListView())
        self._status_input.setInsertPolicy(QComboBox.NoInsert)
        grid.addWidget(self._status_input, r, 1)
        r += 1

        label = self._label("Case Date")
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(label, r, 0)
        self._case_date_input = LeftAlignedDateEdit()
        self._case_date_input.setDate(QDate.currentDate())
        self._case_date_input.setStyleSheet(self._field_style())
        grid.addWidget(self._case_date_input, r, 1)
        r += 1

        layout.addLayout(grid)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        if self._is_edit and self._case:
            delete_btn = QPushButton("Delete Case")
            delete_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {RED}; border: 1px solid {RED};"
                                     f" border-radius: 4px; padding: 8px 16px; font-size: 13px; }}"
                                     f"QPushButton:hover {{ background: {RED}; color: {WHITE}; }}")
            delete_btn.clicked.connect(self._delete_case)
            btn_layout.addWidget(delete_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(self._btn_style(secondary=True))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        save_btn = QPushButton("Save Case")
        save_btn.setStyleSheet(self._btn_style(secondary=False))
        save_btn.clicked.connect(self._try_save)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _required_label(self, text):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        label = self._label(text)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label)
        layout.addWidget(self._required_mark("*"))
        return container

    def _label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {TEXT_DARK}; border: none; background: transparent;")
        return lbl

    def _required_mark(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {RED}; border: none; background: transparent;")
        return lbl
    def _field_style(self):
        return f"""
            QComboBox, QLineEdit, QTextEdit {{
            padding: 6px 8px;
            border: 1px solid {BORDER};
            border-radius: 4px;
            font-size: 13px;
            color: {TEXT_DARK};
            background: {WHITE};
            }}
            QComboBox:hover, QLineEdit:hover, QTextEdit:hover {{
            border: 1px solid {BORDER};
            background: #f0f0f0;
            color: {TEXT_DARK};
            }}
            QComboBox:focus, QLineEdit:focus, QTextEdit:focus {{
            border: 1px solid {BORDER};
            border-color: {STEEL};
            background: {WHITE};
            }}
            /* Popup menu */
            QComboBox QAbstractItemView {{
            outline: none;
            background: {WHITE};
            border: 1px solid {BORDER};
            border-radius: 4px;
            padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
            padding: 6px 8px;
            color: {TEXT_DARK};
            }}
            QComboBox QAbstractItemView::item:hover {{
            background: {NAVY};
            color: {WHITE};
            }}
            QComboBox QAbstractItemView::item:selected {{
            background: {STEEL};
            color: {WHITE};
            }}
        """

    def _btn_style(self, secondary):
        if secondary:
            return f"""
                QPushButton {{ background: transparent; color: {NAVY}; border: 1px solid {NAVY};
                               border-radius: 4px; padding: 8px 20px; font-size: 13px; }}
                QPushButton:hover {{ background: {NAVY}; color: {WHITE}; }}
            """
        return f"""
            QPushButton {{ background: {NAVY}; color: {WHITE}; border: none; border-radius: 4px;
                           padding: 8px 20px; font-size: 13px; font-weight: bold; }}
            QPushButton:hover {{ background: {STEEL}; }}
        """

    def _fill_form(self):
        self._title_input.setText(self._case["title"])
        self._desc_input.setText(self._case["description"])
        idx = self._type_input.findText(self._case["case_type"])
        if idx >= 0:
            self._type_input.setCurrentIndex(idx)
        cidx = self._client_input.findData(self._case["client_id"])
        if cidx >= 0:
            self._client_input.setCurrentIndex(cidx)
        sidx = self._status_input.findText(self._case["status"])
        if sidx >= 0:
            self._status_input.setCurrentIndex(sidx)
        if self._case.get("case_date"):
            dt = QDate.fromString(self._case["case_date"], "yyyy-MM-dd")
            if dt.isValid():
                self._case_date_input.setDate(dt)

    def _try_save(self):
        self._title_error.clear_message()
        self._client_error.clear_message()
        valid = True
        if not self._title_input.text().strip():
            self._title_error.show_message("Title is required")
            valid = False
        if self._client_input.currentIndex() < 0:
            self._client_error.show_message("Please select a client")
            valid = False
        if valid:
            if self._status_input.currentText() == "Closed":
                answer = QMessageBox.question(
                    self, "Confirm Close",
                    "Are you sure you want to close this case? This cannot be undone.",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
                )
                if answer != QMessageBox.Yes:
                    return
            self.accept()

    def _delete_case(self):
        if not self._case:
            return
        reply = QMessageBox.question(
            self,
            "Delete Case",
            f"Are you sure you want to delete case '{self._case['title']}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._repo.delete_case_with_cascade(self._case["case_id"])
            self._case_deleted = True
            self.accept()

    def was_deleted(self):
        return self._case_deleted

    def case_data(self):
        return {
            "title": self._title_input.text().strip(),
            "description": self._desc_input.toPlainText().strip(),
            "case_type": self._type_input.currentText(),
            "case_date": self._case_date_input.date().toString("yyyy-MM-dd"),
            "client_id": self._client_input.currentData(),
            "status": self._status_input.currentText(),
        }


class Casepagemain(QWidget):
    def __init__(self, repo, user, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._user = user
        self._is_lawyer = user["role"] == "lawyer"
        self._filter_status = "All"
        self._filter_type = "All"
        self._build()
        self._load_table()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)

        heading = QLabel("Cases" if self._is_lawyer else "My Cases")
        heading.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        layout.addWidget(heading)
        layout.addSpacing(12)

        if self._is_lawyer:
            self._build_toolbar(layout)

        self._build_table(layout)

    def _build_toolbar(self, layout):
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search by title...")
        self._search.setStyleSheet(f"padding: 6px 10px; border: 1px solid {BORDER}; border-radius: 4px;"
                                   f" font-size: 13px; color: {TEXT_DARK}; background: {WHITE};")
        self._search.textChanged.connect(self._on_filter_changed)
        bar.addWidget(self._search)

        self._status_filter = ArrowComboBox()
        self._status_filter.addItems(["All Status", "Open", "In Progress", "Closed"])
        self._status_filter.setEditable(False)
        self._status_filter.setView(QListView())
        self._status_filter.setInsertPolicy(QComboBox.NoInsert)
        self._status_filter.setStyleSheet(f"""
            QComboBox {{
                padding: 4px 8px;
                border: 1px solid {BORDER};
                border-radius: 4px;
                color: {TEXT_DARK};
                background: {WHITE};
            }}
            QComboBox:hover {{
                border: 1px solid {BORDER};
                background: {WHITE};
                color: {TEXT_DARK};
            }}
            QComboBox:focus {{
                border-color: {STEEL};
            }}
        """)
        self._status_filter.currentTextChanged.connect(self._on_filter_changed)
        bar.addWidget(self._status_filter)

        self._type_filter = ArrowComboBox()
        self._type_filter.addItems(["All Types", "criminal", "civil", "corporate", "family"])
        self._type_filter.setEditable(False)
        self._type_filter.setView(QListView())
        self._type_filter.setInsertPolicy(QComboBox.NoInsert)
        self._type_filter.setStyleSheet(f"""
            QComboBox {{
                padding: 4px 8px;
                border: 1px solid {BORDER};
                border-radius: 4px;
                color: {TEXT_DARK};
                background: {WHITE};
            }}
            QComboBox:hover {{
                border: 1px solid {BORDER};
                background: {WHITE};
                color: {TEXT_DARK};
            }}
            QComboBox:focus {{
                border-color: {STEEL};
            }}
        """)
        self._type_filter.currentTextChanged.connect(self._on_filter_changed)
        bar.addWidget(self._type_filter)

        bar.addStretch()

        new_btn = QPushButton("+ New Case")
        new_btn.setStyleSheet(f"""
            QPushButton {{ background: {NAVY}; color: {WHITE}; border: none; border-radius: 4px;
                           padding: 8px 18px; font-size: 13px; font-weight: bold; }}
            QPushButton:hover {{ background: {STEEL}; }}
        """)
        new_btn.clicked.connect(self._open_create_dialog)
        bar.addWidget(new_btn)

        layout.addLayout(bar)
        layout.addSpacing(12)

    def _build_table(self, layout):
        cols = ["Case #", "Title", "Type", "Status", "Client" if self._is_lawyer else "Lawyer", "Created"]
        self._table = QTableWidget()
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.cellDoubleClicked.connect(self._on_row_double_clicked)
        header = self._table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.Stretch)
        self._table.setStyleSheet(f"""
            QTableWidget {{ background: {WHITE}; border: 1px solid {BORDER}; border-radius: 4px;
                            gridline-color: {BORDER}; font-size: 13px; }}
            QTableWidget::item {{ padding: 6px 8px; color: {TEXT_DARK}; }}
            QHeaderView::section {{ background: {NAVY}; color: {WHITE}; padding: 8px;
                                    font-weight: bold; border: none; font-size: 12px; }}
            QTableWidget::item:alternate {{ background: #F8F9FB; }}
        """)
        layout.addWidget(self._table)

        if not self._is_lawyer:
            self._empty_state = QFrame()
            self._empty_state.setStyleSheet(
                f"background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 8px;"
            )
            empty_layout = QVBoxLayout(self._empty_state)
            empty_layout.setAlignment(Qt.AlignCenter)
            empty_layout.setContentsMargins(24, 40, 24, 40)
            empty_layout.setSpacing(6)
            empty_title = QLabel("No cases yet")
            empty_title.setAlignment(Qt.AlignCenter)
            empty_title.setStyleSheet(
                f"font-size: 16px; font-weight: bold; color: {TEXT_DARK}; border: none; background: transparent;"
            )
            empty_layout.addWidget(empty_title)
            empty_sub = QLabel("Your lawyer will create cases for you.")
            empty_sub.setAlignment(Qt.AlignCenter)
            empty_sub.setStyleSheet(
                f"font-size: 13px; color: {TEXT_GRAY}; border: none; background: transparent;"
            )
            empty_layout.addWidget(empty_sub)
            layout.addWidget(self._empty_state)
            self._empty_state.setVisible(False)

    def _load_table(self):
        cases = self._filtered_cases()
        self._table.setRowCount(len(cases))
        for row, case in enumerate(cases):
            self._table.setItem(row, 0, QTableWidgetItem(case["case_number"]))
            self._table.setItem(row, 1, QTableWidgetItem(case["title"]))
            self._table.setItem(row, 2, QTableWidgetItem(case["case_type"]))
            self._table.setCellWidget(row, 3, _status_badge(case["status"]))
            person_id = case["client_id"] if self._is_lawyer else case["lawyer_id"]
            person = self._repo.get_user(person_id)
            person_name = f"{person['first_name']} {person['last_name']}" if person else "—"
            self._table.setItem(row, 4, QTableWidgetItem(person_name))
            self._table.setItem(row, 5, QTableWidgetItem(case["created_at"][:10]))
        self._update_empty_state()

    def _update_empty_state(self):
        if not self._is_lawyer:
            has_cases = self._table.rowCount() > 0
            self._table.setVisible(has_cases)
            self._empty_state.setVisible(not has_cases)

    def _filtered_cases(self):
        cases = (self._repo.get_cases_for_lawyer(self._user["user_id"])
                 if self._is_lawyer
                 else self._repo.get_cases_for_client(self._user["user_id"]))
        search = self._search.text().strip().lower() if self._is_lawyer else ""
        if search:
            cases = [c for c in cases if search in c["title"].lower()]
        if self._filter_status != "All Status" and self._filter_status != "All":
            cases = [c for c in cases if c["status"] == self._filter_status]
        if self._filter_type != "All Types" and self._filter_type != "All":
            cases = [c for c in cases if c["case_type"] == self._filter_type]
        return cases

    def _on_filter_changed(self):
        if self._is_lawyer:
            self._filter_status = self._status_filter.currentText()
            self._filter_type = self._type_filter.currentText()
        self._load_table()

    def _on_row_double_clicked(self, row, _col):
        case_number = self._table.item(row, 0).text()
        cases = self._filtered_cases()
        case = next((c for c in cases if c["case_number"] == case_number), None)
        if case is None:
            return
        self._open_case_detail(case)

    def _open_case_detail(self, case):
        from case_files import CaseDetailView
        while True:
            dlg = CaseDetailView(self._repo, case, self._user, parent=self)
            if dlg.exec() == 2:
                self._open_edit_dialog(case)
                case = self._repo.get_case(case["case_id"])
                if case is None:
                    break
            else:
                break
        self._load_table()

    def _open_create_dialog(self):
        dialog = CaseForm(self._repo, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.case_data()
        data["lawyer_id"] = self._user["user_id"]
        new_case = self._repo.create_case(data)
        client = self._repo.get_user(data["client_id"])
        client_name = f"{client['first_name']} {client['last_name']}" if client else "a client"
        self._repo.create_notification({
            "user_id": data["client_id"],
            "title": "New Case Created",
            "message": f"Your case '{data['title']}' has been opened by {self._user['first_name']} {self._user['last_name']}.",
            "notification_type": "case_created",
            "reference_id": new_case["case_id"],
        })
        self._load_table()

    def _open_edit_dialog(self, case):
        dialog = CaseForm(self._repo, case, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        if dialog.was_deleted():
            self._load_table()
            return
        data = dialog.case_data()
        self._repo.update_case(case["case_id"], **data)
        self._load_table()

    def _show_detail_dialog(self, case):
        client = self._repo.get_user(case["client_id"])
        client_name = f"{client['first_name']} {client['last_name']}" if client else "—"
        lawyer = self._repo.get_user(case["lawyer_id"])
        lawyer_name = f"{lawyer['first_name']} {lawyer['last_name']}" if lawyer else "—"
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Case Details — {case['case_number']}")
        dlg.resize(520, 400)
        dlg.setStyleSheet(f"background: {WHITE};")
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)

        grid = QGridLayout()
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(12)
        grid.setColumnStretch(1, 1)

        fields = [
            ("Case #", case["case_number"]),
            ("Title", case["title"]),
            ("Type", case["case_type"].capitalize()),
            ("Status", case["status"]),
            ("Client", client_name),
            ("Lawyer", lawyer_name),
            ("Description", case["description"] or "No description."),
            ("Created", case["created_at"][:10]),
        ]
        for r, (label, value) in enumerate(fields):
            lbl = QLabel(label)
            lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {NAVY}; border: none;")
            val = QLabel(value)
            val.setWordWrap(True)
            val.setStyleSheet(f"font-size: 13px; color: {TEXT_DARK}; border: none;")
            grid.addWidget(lbl, r, 0, Qt.AlignRight | Qt.AlignTop)
            grid.addWidget(val, r, 1)

        layout.addLayout(grid)
        layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {NAVY}; border: 1px solid {NAVY};
                           border-radius: 4px; padding: 8px 20px; font-size: 13px; }}
            QPushButton:hover {{ background: {NAVY}; color: {WHITE}; }}
        """)
        close_btn.clicked.connect(dlg.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dlg.exec()


# ═══════════════════════════════════════════════════════════════════════════
# Appointment Scheduling
# ═══════════════════════════════════════════════════════════════════════════

class MonthCalendar(QFrame):
    date_selected = Signal(str)

    DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    MONTHS = ["January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._today = datetime.now()
        self._year = self._today.year
        self._month = self._today.month
        self._selected = self._today.strftime("%Y-%m-%d")
        self._appt_dates = set()
        self._day_btns = []
        self._build()
        self._render()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        nav = QHBoxLayout()
        nav.setSpacing(4)
        prev = QPushButton("◀")
        prev.setFixedSize(32, 28)
        prev.setCursor(Qt.PointingHandCursor)
        prev.setStyleSheet(
            f"background: {WHITE}; color: {NAVY}; border: 1px solid {BORDER};"
            f" border-radius: 4px; font-size: 14px;"
        )
        prev.clicked.connect(self._prev_month)
        nav.addWidget(prev)

        self._title = QLabel()
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {NAVY};"
            f" background: {WHITE}; border: none; padding: 4px 0;"
        )
        nav.addWidget(self._title, stretch=1)

        nxt = QPushButton("▶")
        nxt.setFixedSize(32, 28)
        nxt.setCursor(Qt.PointingHandCursor)
        nxt.setStyleSheet(
            f"background: {WHITE}; color: {NAVY}; border: 1px solid {BORDER};"
            f" border-radius: 4px; font-size: 14px;"
        )
        nxt.clicked.connect(self._next_month)
        nav.addWidget(nxt)
        layout.addLayout(nav)

        grid = QGridLayout()
        grid.setSpacing(2)
        for i, d in enumerate(self.DAYS):
            lbl = QLabel(d)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedSize(42, 22)
            lbl.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {TEXT_DARK}; border: none; background: {WHITE};")
            grid.addWidget(lbl, 0, i)

        for r in range(6):
            for c in range(7):
                btn = QPushButton()
                btn.setFixedSize(42, 32)
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(lambda chk, row=r, col=c: self._on_click(row, col))
                grid.addWidget(btn, r + 1, c)
                self._day_btns.append(((r, c), btn))
        layout.addLayout(grid)

    def set_appointment_dates(self, dates):
        self._appt_dates = set(dates)
        self._render()

    def set_month(self, year, month):
        self._year = int(year)
        self._month = int(month)
        self._render()

    def select_day(self, day):
        day = int(day)
        date_str = f"{self._year}-{self._month:02d}-{day:02d}"
        self._selected = date_str
        self._render()
        self.date_selected.emit(date_str)

    def selected_date(self):
        return self._selected

    def _prev_month(self):
        if self._month == 1:
            self._month, self._year = 12, self._year - 1
        else:
            self._month -= 1
        self._render()

    def _next_month(self):
        if self._month == 12:
            self._month, self._year = 1, self._year + 1
        else:
            self._month += 1
        self._render()

    def _render(self):
        self._title.setText(f"{self.MONTHS[self._month - 1]} {self._year}")
        weeks = calendar.monthcalendar(self._year, self._month)
        today_str = self._today.strftime("%Y-%m-%d")
        for (r, c), btn in self._day_btns:
            day = weeks[r][c] if r < len(weeks) else 0
            if day == 0:
                btn.setText(""); btn.setEnabled(False)
                btn.setStyleSheet("background: transparent; border: none;")
                continue
            ds = f"{self._year}-{self._month:02d}-{day:02d}"
            btn.setEnabled(True)
            if ds == self._selected:
                btn.setText(str(day))
                bg = f"background: {NAVY}; color: {WHITE}; border: none"
            elif ds == today_str:
                btn.setText(str(day))
                bg = f"background: transparent; color: {NAVY}; border: 2px solid {NAVY}; font-weight: bold"
            elif ds in self._appt_dates:
                btn.setText(f"{day}\n•")
                bg = f"background: #E8F0FE; color: {NAVY}; font-weight: bold; border: none"
            else:
                btn.setText(str(day))
                bg = f"background: transparent; color: {TEXT_DARK}; border: none"
            btn.setStyleSheet(f"{bg}; border-radius: 4px; font-size: 13px;")

    def _on_click(self, row, col):
        weeks = calendar.monthcalendar(self._year, self._month)
        if row < len(weeks) and weeks[row][col] != 0:
            day = weeks[row][col]
            date_str = f"{self._year}-{self._month:02d}-{day:02d}"
            self._selected = date_str
            self.date_selected.emit(date_str)
        self._render()


class AppointmentDialog(QDialog):
    def __init__(self, repo, user, date_str, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._user = user
        self._date_str = date_str
        self._is_lawyer = user["role"] == "lawyer"
        self.setWindowTitle("New Appointment")
        self.resize(480, 440)
        self._build()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(8)

        grid = QGridLayout()
        grid.setVerticalSpacing(6)
        grid.setHorizontalSpacing(10)
        grid.setColumnStretch(1, 1)

        r = 0
        grid.addWidget(self._required_label("Title:"), r, 0)
        self._title = QLineEdit()
        self._title.setStyleSheet(self._fs())
        grid.addWidget(self._title, r, 1)
        r += 1

        if not self._is_lawyer:
            grid.addWidget(self._required_label("Lawyer:"), r, 0)
            self._lawyer = ArrowComboBox()
            for law in self._repo.get_all_lawyers():
                self._lawyer.addItem(f"{law['first_name']} {law['last_name']}", law["user_id"])
            self._lawyer.setStyleSheet(self._fs())
            grid.addWidget(self._lawyer, r, 1)
            r += 1

        grid.addWidget(self._lbl("Case:"), r, 0)
        self._case = ArrowComboBox()
        self._case.addItem("None", "")
        for c in (self._repo.get_cases_for_client(self._user["user_id"])
                  if not self._is_lawyer else self._repo.get_cases_for_lawyer(self._user["user_id"])):
            self._case.addItem(f"{c['case_number']} – {c['title']}", c["case_id"])
        self._case.setStyleSheet(self._fs())
        grid.addWidget(self._case, r, 1)
        r += 1

        grid.addWidget(self._lbl("Date:"), r, 0)
        date_lbl = QLabel(self._date_str)
        date_lbl.setStyleSheet(f"font-size: 13px; color: {TEXT_DARK}; border: none;")
        grid.addWidget(date_lbl, r, 1)
        r += 1

        grid.addWidget(self._required_label("Time:"), r, 0)
        self._time = ArrowComboBox()
        for h in range(8, 19):
            for m in (0, 30):
                self._time.addItem(f"{h:02d}:{m:02d}")
        self._time.setStyleSheet(self._fs())
        grid.addWidget(self._time, r, 1)
        r += 1

        grid.addWidget(self._lbl("Duration:"), r, 0)
        self._duration = ArrowComboBox()
        for mins in (30, 45, 60, 90, 120):
            self._duration.addItem(f"{mins} min", mins)
        self._duration.setCurrentIndex(2)
        self._duration.setStyleSheet(self._fs())
        grid.addWidget(self._duration, r, 1)
        r += 1

        grid.addWidget(self._lbl("Notes:"), r, 0, Qt.AlignTop)
        self._notes = QTextEdit()
        self._notes.setMaximumHeight(60)
        self._notes.setStyleSheet(self._fs())
        grid.addWidget(self._notes, r, 1)
        r += 1

        layout.addLayout(grid)
        self._error = _ErrorLabel()
        layout.addWidget(self._error)
        layout.addStretch()

        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(f"QPushButton {{ background: transparent; color: {NAVY}; border: 1px solid {NAVY};"
                             f" border-radius: 4px; padding: 8px 20px; font-size: 13px; }}"
                             f"QPushButton:hover {{ background: {NAVY}; color: {WHITE}; }}")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        save = QPushButton("Save Appointment")
        save.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none; border-radius: 4px;"
                           f" padding: 8px 20px; font-size: 13px; font-weight: bold; }}"
                           f"QPushButton:hover {{ background: {STEEL}; }}")
        save.clicked.connect(self._try_save)
        btns.addWidget(save)
        layout.addLayout(btns)

    def _lbl(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {TEXT_DARK}; border: none;")
        return lbl

    def _required_label(self, text):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        label = self._lbl(text)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(label)
        mark = QLabel("*")
        mark.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {RED}; border: none;")
        layout.addWidget(mark)
        return container

    def _fs(self):
        return f"padding: 6px 8px; border: 1px solid {BORDER}; border-radius: 4px; font-size: 13px; color: {TEXT_DARK}; background: {WHITE};"

    def _try_save(self):
        self._error.clear_message()
        if not self._title.text().strip():
            self._error.show_message("Title is required"); return
        if not self._is_lawyer and self._lawyer.currentData() is None:
            self._error.show_message("Please select a lawyer"); return
        if not self._time.currentText():
            self._error.show_message("Please select a time"); return
        self.accept()

    def appointment_data(self):
        return {
            "title": self._title.text().strip(),
            "lawyer_id": self._user["user_id"] if self._is_lawyer else self._lawyer.currentData(),
            "date": self._date_str,
            "start_time": self._time.currentText(),
            "duration_minutes": self._duration.currentData() or 60,
            "notes": self._notes.toPlainText().strip(),
            "case_id": self._case.currentData() or "",
        }


class CalendarPage(QWidget):
    def __init__(self, repo, user, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._user = user
        self._is_lawyer = user["role"] == "lawyer"
        self._selected_date = datetime.now().strftime("%Y-%m-%d")
        self._build()
        self._refresh_all()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 16)
        main_layout.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(0)
        self._calendar = MonthCalendar()
        self._calendar.setMaximumWidth(380)
        self._calendar.date_selected.connect(self._on_date_selected)
        left.addWidget(self._calendar)
        left.addStretch()
        main_layout.addLayout(left)

        right = QVBoxLayout()
        right.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("Appointments" if self._is_lawyer else "My Appointments")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        header.addWidget(title)
        header.addStretch()
        if not self._is_lawyer:
            new_btn = QPushButton("+ Request Appointment")
            new_btn.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none;"
                                  f" border-radius: 4px; padding: 8px 16px; font-size: 12px; font-weight: bold; }}"
                                  f"QPushButton:hover {{ background: {STEEL}; }}")
            new_btn.clicked.connect(self._open_create)
            header.addWidget(new_btn)
        right.addLayout(header)

        self._date_label = QLabel()
        self._date_label.setStyleSheet(f"font-size: 14px; color: {STEEL}; font-weight: bold; border: none;")
        right.addWidget(self._date_label)

        self._status_banner = QLabel()
        self._status_banner.setVisible(False)
        self._status_banner.setStyleSheet(f"background: #E8F5E9; color: {GREEN}; border: 1px solid #A5D6A7;"
                                          f" border-radius: 4px; padding: 8px 10px; font-size: 12px; font-weight: bold;")
        right.addWidget(self._status_banner)

        self._appt_scroll = QScrollArea()
        self._appt_scroll.setWidgetResizable(True)
        self._appt_scroll.setStyleSheet(f"border: none; background: transparent;")
        self._appt_container = QWidget()
        self._appt_layout = QVBoxLayout(self._appt_container)
        self._appt_layout.setContentsMargins(0, 0, 0, 0)
        self._appt_layout.setSpacing(6)
        self._appt_layout.addStretch()
        self._appt_scroll.setWidget(self._appt_container)
        right.addWidget(self._appt_scroll, stretch=1)

        main_layout.addLayout(right, stretch=1)

    def _refresh_all(self):
        self._sync_calendar_dots()
        self._on_date_selected(self._selected_date)

    def _sync_calendar_dots(self):
        dates = set()
        appts = (self._repo.get_appointments_for_lawyer(self._user["user_id"])
                 if self._is_lawyer
                 else self._repo.get_appointments_for_client(self._user["user_id"]))
        for a in appts:
            dates.add(a["date"])
        self._calendar.set_appointment_dates(dates)

    def _on_date_selected(self, date_str):
        self._selected_date = date_str
        self._date_label.setText(f"Appointments for {date_str}")
        self._refresh_appointments(date_str)

    def _show_status_message(self, message, success=True):
        self._status_banner.setText(message)
        self._status_banner.setVisible(True)
        self._status_banner.setStyleSheet(
            f"background: {'#E8F5E9' if success else '#FDECEC'}; color: {'#15803D' if success else '#B91C1C'};"
            f" border: 1px solid {'#A5D6A7' if success else '#F5C2C7'}; border-radius: 4px;"
            f" padding: 8px 10px; font-size: 12px; font-weight: bold;"
        )

    def _refresh_appointments(self, date_str):
        clear_layout(self._appt_layout)
        appts = self._repo.get_appointments_for_date(
            self._user["user_id"], self._user["role"], date_str
        )
        if not appts:
            empty_frame = QFrame()
            empty_frame.setStyleSheet(
                f"background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 8px;"
            )
            empty_layout = QVBoxLayout(empty_frame)
            empty_layout.setAlignment(Qt.AlignCenter)
            empty_layout.setContentsMargins(24, 40, 24, 40)
            empty_layout.setSpacing(8)
            icon_lbl = QLabel("🗓️")
            icon_lbl.setAlignment(Qt.AlignCenter)
            icon_lbl.setStyleSheet(f"font-size: 28px; border: none; background: transparent;")
            empty_layout.addWidget(icon_lbl)
            empty_text = QLabel("No appointments for this date.")
            empty_text.setAlignment(Qt.AlignCenter)
            empty_text.setStyleSheet(
                f"color: {TEXT_GRAY}; font-size: 14px; border: none; background: transparent;"
            )
            empty_layout.addWidget(empty_text)
            self._appt_layout.addWidget(empty_frame)
        else:
            for a in appts:
                self._appt_layout.addWidget(self._appointment_card(a))
        self._appt_layout.addStretch()

    def navigate_to_date(self, date_str):
        date = QDate.fromString(date_str, "yyyy-MM-dd")
        if not date.isValid():
            return
        self._calendar.set_month(date.year(), date.month())
        self._calendar.select_day(date.day())
        self._on_date_selected(date_str)

    def refresh(self):
        self._refresh_all()

    def _appointment_card(self, appt):
        frame = QFrame()
        frame.setStyleSheet(f"background: {WHITE}; border: 1px solid {BORDER}; border-radius: 6px;")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 30))
        frame.setGraphicsEffect(shadow)
        hl = QHBoxLayout(frame)
        hl.setContentsMargins(12, 8, 12, 8)

        # info layout (title, detail, notes)
        info = QVBoxLayout()
        tl = QLabel(appt["title"])
        tl.setStyleSheet(f"font-weight: bold; color: {TEXT_DARK}; font-size: 13px; border: none;")
        info.addWidget(tl)
        detail = QLabel(f"{appt['start_time']}  ·  {appt['duration_minutes']} min")
        detail.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 12px; border: none;")
        info.addWidget(detail)
        if appt.get("notes"):
            n = QLabel(appt["notes"])
            n.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 11px; font-style: italic; border: none;")
            n.setWordWrap(True)
            info.addWidget(n)
        hl.addLayout(info)
        hl.addStretch()

        actions = QWidget()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(6)

        badge = _status_badge(appt["status"])
        actions_layout.addWidget(badge)
        actions._badge = badge

        # ---- Buttons ----
        btn_no_border = """
        QPushButton {
            background: transparent;
            color: %s;
            border: 0px;
            border-style: none;
            outline: 0px;
            box-shadow: none;
            border-radius: 0px;
            padding: 2px 10px;
            font-size: 11px;
        }
        QPushButton:hover {
            background: %s;
            color: %s;
            border: 0px;
            outline: 0px;
        }
        QPushButton:pressed, QPushButton:focus {
            border: 0px;
            outline: 0px;
        }
        """

        if self._is_lawyer and appt["status"] == "Requested":
            decline_btn = QPushButton("Decline")
            decline_btn.setFixedHeight(28)
            decline_btn.setStyleSheet(btn_no_border % (RED, RED, WHITE))
            decline_btn.clicked.connect(lambda chk, a=appt, ac=actions: self._decline(a, ac))
            actions_layout.addWidget(decline_btn)

            approve_btn = QPushButton("Approve")
            approve_btn.setFixedHeight(28)
            approve_btn.setStyleSheet("""
            QPushButton {
                background: %s;
                color: %s;
                border: 0px;
                outline: 0px;
                border-radius: 0px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #047857;
                color: %s;
                border: 0px;
                outline: 0px;
            }
            QPushButton:pressed, QPushButton:focus {
                border: 0px;
                outline: 0px;
            }
        """ % (GREEN, WHITE, WHITE))
            approve_btn.clicked.connect(lambda chk, a=appt, ac=actions: self._approve(a, ac))
            actions_layout.addWidget(approve_btn)

        if self._is_lawyer and appt["status"] == "Approved":
            complete_btn = QPushButton("Complete")
            complete_btn.setFixedHeight(28)
            complete_btn.setStyleSheet("""
            QPushButton {
                background: %s;
                color: %s;
                border: 0px;
                outline: 0px;
                border-radius: 0px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: %s;
                color: %s;
                border: 0px;
                outline: 0px;
            }
            QPushButton:pressed, QPushButton:focus {
                border: 0px;
                outline: 0px;
            }
        """ % (STEEL, WHITE, NAVY, WHITE))
            complete_btn.clicked.connect(lambda chk, a=appt, ac=actions: self._complete(a, ac))
            actions_layout.addWidget(complete_btn)

        if not self._is_lawyer and appt["status"] == "Requested":
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setFixedHeight(28)
            cancel_btn.setStyleSheet(btn_no_border % (RED, RED, WHITE))
            cancel_btn.clicked.connect(lambda chk, a=appt, ac=actions: self._cancel(a, ac))
            actions_layout.addWidget(cancel_btn)

        hl.addWidget(actions)
        return frame

    def _open_create(self):
        dlg = AppointmentDialog(self._repo, self._user, self._selected_date, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.appointment_data()
        data["client_id"] = self._user["user_id"]
        data["status"] = "Requested"
        conflict = self._repo.find_appointment_conflict({
            "lawyer_id": data["lawyer_id"], "date": data["date"],
            "start_time": data["start_time"], "duration_minutes": data["duration_minutes"]
        })
        if conflict:
            QMessageBox.warning(self, "Schedule Conflict",
                f"The selected time conflicts with '{conflict['title']}' "
                f"({conflict['date']} {conflict['start_time']}).")
            return
        appt = self._repo.create_appointment(data)
        self._repo.create_notification({
            "user_id": data["lawyer_id"],
            "title": "New Appointment Request",
            "message": f"{self._user['first_name']} {self._user['last_name']} "
                       f"requested an appointment: '{data['title']}' on {data['date']}.",
            "notification_type": "appointment_requested",
            "reference_id": appt["appointment_id"],
        })
        self._show_status_message("Appointment request sent to the lawyer.", success=True)
        self._refresh_all()

    def _replace_actions(self, actions_widget, text, color):
        layout = actions_widget.layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_sub_layout(item.layout())
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold; border: none;")
        layout.addWidget(lbl)

    def _clear_sub_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_sub_layout(item.layout())

    _STATUS_INFO = {
        "Approved":  ("Appointment Approved", "approved", GREEN),
        "Declined":  ("Appointment Declined", "declined", RED),
        "Completed": ("Appointment Completed", "completed", STEEL),
        "Cancelled": ("Appointment Cancelled", "cancelled", TEXT_GRAY),
    }

    def _update_appointment_status(self, appt, new_status, actions=None):
        notif_title, verb, color = self._STATUS_INFO[new_status]
        self._repo.update_appointment(appt["appointment_id"], status=new_status)
        self._repo.create_notification({
            "user_id": appt["client_id"],
            "title": notif_title,
            "message": f"Your appointment '{appt['title']}' on {appt['date']} has been {verb}.",
            "notification_type": notif_title.lower().replace(" ", "_"),
            "reference_id": appt["appointment_id"],
        })
        if actions is not None and hasattr(actions, "_badge"):
            badge = actions._badge
            colors = {
                "Approved": (GREEN, WHITE),
                "Declined": (RED, WHITE),
                "Completed": (STEEL, WHITE),
                "Cancelled": (TEXT_GRAY, WHITE),
            }
            bg, fg = colors.get(new_status, (TEXT_GRAY, WHITE))
            badge.setText(new_status)
            badge.setStyleSheet(
                f"background: {bg}; color: {fg}; padding: 2px 10px; "
                f"border-radius: 10px; font-size: 11px; font-weight: bold;"
            )
            action_layout = actions.layout()
            for i in range(action_layout.count() - 1, 0, -1):
                item = action_layout.takeAt(i)
                if item.widget():
                    item.widget().deleteLater()
            self._show_status_message(f"Appointment {verb} and the client has been notified.", success=True)
            self._sync_calendar_dots()
        else:
            self._show_status_message(f"Appointment {verb} and the client has been notified.", success=True)
            self._refresh_all()

    def _approve(self, appt, actions=None):
        conflict = self._repo.find_appointment_conflict({
            "lawyer_id": appt["lawyer_id"], "date": appt["date"],
            "start_time": appt["start_time"], "duration_minutes": appt["duration_minutes"],
            "exclude_id": appt["appointment_id"]
        })
        if conflict:
            QMessageBox.warning(self, "Schedule Conflict",
                f"Cannot approve: conflicts with '{conflict['title']}' "
                f"({conflict['date']} {conflict['start_time']}).")
            return
        self._update_appointment_status(appt, "Approved", actions)

    def _decline(self, appt, actions=None):
        answer = QMessageBox.question(
            self, "Confirm Decline",
            "Are you sure you want to decline this appointment?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._update_appointment_status(appt, "Declined", actions)

    def _complete(self, appt, actions=None):
        self._update_appointment_status(appt, "Completed", actions)

    def _cancel(self, appt, actions=None):
        answer = QMessageBox.question(
            self, "Confirm Cancel",
            "Are you sure you want to cancel this appointment?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._update_appointment_status(appt, "Cancelled", actions)

# ═══════════════════════════════════════════════════════════════════════════
# Invoicing & Payment
# ═══════════════════════════════════════════════════════════════════════════

class InvoiceFormDialog(QDialog):
    def __init__(self, repo, user, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._user = user
        self.setWindowTitle("New Invoice")
        self.resize(460, 360)
        self._build()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(8)

        grid = QGridLayout()
        grid.setVerticalSpacing(6)
        grid.setHorizontalSpacing(10)
        grid.setColumnStretch(1, 1)

        r = 0
        grid.addWidget(self._lbl("* Case:"), r, 0)
        self._case = ArrowComboBox()
        for c in self._repo.get_cases_for_lawyer(self._user["user_id"]):
            client = self._repo.get_user(c["client_id"])
            cn = f"{client['first_name']} {client['last_name']}" if client else "—"
            self._case.addItem(f"{c['case_number']} – {c['title']} ({cn})", c["case_id"])
        self._case.setStyleSheet(self._fs())
        grid.addWidget(self._case, r, 1)
        r += 1

        grid.addWidget(self._lbl("* Description:"), r, 0)
        self._desc = QLineEdit()
        self._desc.setStyleSheet(self._fs())
        grid.addWidget(self._desc, r, 1)
        r += 1

        grid.addWidget(self._lbl("* Amount ($):"), r, 0)
        self._amount = QLineEdit()
        self._amount.setStyleSheet(self._fs())
        grid.addWidget(self._amount, r, 1)
        r += 1

        grid.addWidget(self._lbl("* Due Date:"), r, 0)
        self._due = LeftAlignedDateEdit()
        self._due.setDate(QDate.currentDate().addDays(30))
        self._due.setStyleSheet(self._fs())
        grid.addWidget(self._due, r, 1)
        r += 1

        layout.addLayout(grid)
        self._error = _ErrorLabel()
        layout.addWidget(self._error)
        layout.addStretch()

        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(f"QPushButton {{ background: transparent; color: {NAVY}; border: 1px solid {NAVY};"
                             f" border-radius: 4px; padding: 8px 20px; font-size: 13px; }}"
                             f"QPushButton:hover {{ background: {NAVY}; color: {WHITE}; }}")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        save = QPushButton("Create Invoice")
        save.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none; border-radius: 4px;"
                           f" padding: 8px 20px; font-size: 13px; font-weight: bold; }}"
                           f"QPushButton:hover {{ background: {STEEL}; }}")
        save.clicked.connect(self._try_save)
        btns.addWidget(save)
        layout.addLayout(btns)

    def _lbl(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {TEXT_DARK}; border: none;")
        return lbl

    def _fs(self):
        return f"padding: 6px 8px; border: 1px solid {BORDER}; border-radius: 4px; font-size: 13px; color: {TEXT_DARK}; background: {WHITE};"

    def _try_save(self):
        self._error.clear_message()
        if self._case.currentData() is None:
            self._error.show_message("Please select a case"); return
        if not self._desc.text().strip():
            self._error.show_message("Description is required"); return
        try:
            amt = float(self._amount.text().strip())
            if amt <= 0:
                raise ValueError
        except ValueError:
            self._error.show_message("Please enter a valid amount"); return
        if not self._due.date().isValid():
            self._error.show_message("Please select a due date"); return
        self.accept()

    def invoice_data(self):
        case_data = self._case.currentData()
        case = self._repo.get_case(case_data) if case_data else {}
        return {
            "case_id": case_data or "",
            "client_id": case.get("client_id", ""),
            "description": self._desc.text().strip(),
            "amount": float(self._amount.text().strip()),
            "due_date": self._due.date().toString("yyyy-MM-dd"),
        }


class PaymentDialog(QDialog):
    def __init__(self, repo, client_id, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._client_id = client_id
        self._selected_ids = []
        self.setWindowTitle("Pay Invoices")
        self.resize(500, 430)
        self._build()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._page_select())
        self._stack.addWidget(self._page_card())
        self._stack.addWidget(self._page_otp())
        self._stack.addWidget(self._page_confirm())
        layout.addWidget(self._stack)

        self._error = _ErrorLabel()
        layout.addWidget(self._error)

        nav = QHBoxLayout()
        self._back_btn = QPushButton("← Back")
        self._back_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {NAVY}; border: none; font-size: 13px; }}"
                                     f"QPushButton:hover {{ color: {STEEL}; }}")
        self._back_btn.clicked.connect(self._go_back)
        self._back_btn.hide()
        nav.addWidget(self._back_btn)
        nav.addStretch()
        self._next_btn = QPushButton("Next →")
        self._next_btn.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none; border-radius: 4px;"
                                     f" padding: 8px 22px; font-size: 13px; font-weight: bold; }}"
                                     f"QPushButton:hover {{ background: {STEEL}; }}")
        self._next_btn.clicked.connect(self._go_next)
        nav.addWidget(self._next_btn)
        layout.addLayout(nav)

    def _page_select(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("Select invoices to pay:")
        lbl.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        layout.addWidget(lbl)
        layout.addSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"border: 1px solid {BORDER}; border-radius: 4px; background: {WHITE};")
        container = QWidget()
        self._check_layout = QVBoxLayout(container)
        self._check_layout.setContentsMargins(8, 8, 8, 8)
        self._check_layout.setSpacing(4)
        self._check_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)
        self._total_label = QLabel()
        self._total_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {NAVY}; border: none;")
        layout.addWidget(self._total_label)
        return page

    def _page_card(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("Enter card details:")
        lbl.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        layout.addWidget(lbl)
        layout.addSpacing(12)

        grid = QGridLayout()
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(10)
        grid.addWidget(QLabel("* Card Number:"), 0, 0)
        grid.itemAt(grid.count() - 1).widget().setStyleSheet(
            f"font-size: 13px; font-weight: 500; color: {TEXT_DARK}; border: none;"
        )
        self._card_num = QLineEdit()
        self._card_num.setPlaceholderText("1234 5678 9012 3456")
        self._card_num.setStyleSheet(f"padding: 6px 8px; border: 1px solid {BORDER}; border-radius: 4px;")
        grid.addWidget(self._card_num, 0, 1)

        grid.addWidget(QLabel("* Expiry (MM/YY):"), 1, 0)
        grid.itemAt(grid.count() - 1).widget().setStyleSheet(
            f"font-size: 13px; font-weight: 500; color: {TEXT_DARK}; border: none;"
        )
        self._expiry = QLineEdit()
        self._expiry.setPlaceholderText("MM/YY")
        self._expiry.setFixedWidth(80)
        self._expiry.setStyleSheet(f"padding: 6px 8px; border: 1px solid {BORDER}; border-radius: 4px;")
        grid.addWidget(self._expiry, 1, 1)

        grid.addWidget(QLabel("* CVV:"), 2, 0)
        grid.itemAt(grid.count() - 1).widget().setStyleSheet(
            f"font-size: 13px; font-weight: 500; color: {TEXT_DARK}; border: none;"
        )
        self._cvv = QLineEdit()
        self._cvv.setPlaceholderText("123")
        self._cvv.setEchoMode(QLineEdit.Password)
        self._cvv.setFixedWidth(80)
        self._cvv.setStyleSheet(f"padding: 6px 8px; border: 1px solid {BORDER}; border-radius: 4px;")
        grid.addWidget(self._cvv, 2, 1)

        layout.addLayout(grid)
        layout.addStretch()
        return page

    def _page_otp(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        lbl = QLabel("Enter the 6-digit verification code")
        lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        layout.addWidget(lbl)

        sub = QLabel("A code was sent to your registered device")
        sub.setStyleSheet(f"font-size: 12px; color: {TEXT_GRAY}; border: none;")
        layout.addWidget(sub)

        otp_row = QHBoxLayout()
        otp_row.setSpacing(8)
        otp_row.setAlignment(Qt.AlignCenter)
        self._otp_digits = []
        for i in range(6):
            field = QLineEdit()
            field.setFixedSize(40, 44)
            field.setMaxLength(1)
            field.setAlignment(Qt.AlignCenter)
            field.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {TEXT_DARK};"
                               f" border: 2px solid {BORDER}; border-radius: 6px;"
                               f" background: {WHITE}; padding: 0px;")
            field.textChanged.connect(lambda txt, idx=i: self._on_otp_digit_changed(idx, txt))
            self._otp_digits.append(field)
            otp_row.addWidget(field)
        layout.addLayout(otp_row)
        layout.addStretch()
        self._otp_digits[0].setFocus()
        return page

    def _on_otp_digit_changed(self, idx, text):
        if text and idx < 5:
            self._otp_digits[idx + 1].setFocus()

    def _page_confirm(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("Confirm payment:")
        lbl.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        layout.addWidget(lbl)
        layout.addSpacing(8)
        self._summary_label = QLabel()
        self._summary_label.setStyleSheet(f"font-size: 13px; color: {TEXT_DARK}; border: none; padding: 12px;"
                                          f" background: #F8F9FB; border-radius: 4px;")
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)
        layout.addStretch()
        return page

    def exec(self):
        self._populate_selection()
        self._stack.setCurrentIndex(0)
        self._back_btn.hide()
        self._next_btn.setText("Next →")
        self._error.clear_message()
        for field in self._otp_digits:
            field.clear()
        self._otp_digits[0].setFocus()
        return super().exec()

    def _populate_selection(self):
        while self._check_layout.count():
            item = self._check_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._checks = []
        invoices = [inv for inv in self._repo.get_invoices_for_client(self._client_id)
                    if inv["status"] != "Paid"]
        if not invoices:
            self._check_layout.insertWidget(0, QLabel("No unpaid invoices."))
            self._total_label.setText("Total: $0.00")
            return
        for inv in invoices:
            cb = QCheckBox(f"{inv['invoice_number']} — {inv['description']} (${inv['amount']:,.2f})")
            cb.setStyleSheet(f"font-size: 12px; color: {TEXT_DARK}; border: 1px solid {BORDER}; border-radius: 4px; padding: 6px;")
            cb.toggled.connect(self._update_total)
            self._check_layout.insertWidget(self._check_layout.count() - 1, cb)
            self._checks.append((cb, inv))
        self._check_layout.addStretch()
        self._update_total()

    def _update_total(self):
        total = sum(inv["amount"] for cb, inv in self._checks if cb.isChecked())
        self._total_label.setText(f"Total: ${total:,.2f}")

    def _go_next(self):
        idx = self._stack.currentIndex()
        if idx == 0:
            self._selected_ids = [inv["invoice_id"] for cb, inv in self._checks if cb.isChecked()]
            if not self._selected_ids:
                self._error.show_message("Please select at least one invoice")
                return
            self._error.clear_message()
            self._stack.setCurrentIndex(1)
            self._back_btn.show()
            self._next_btn.setText("Next →")
        elif idx == 1:
            card_num = self._card_num.text().strip()
            cvv = self._cvv.text().strip()
            if not card_num:
                self._error.show_message("Card number is required"); return
            if not card_num.isdigit() or len(card_num) != 16:
                self._error.show_message("Card number must be 16 digits"); return
            if not self._expiry.text().strip():
                self._error.show_message("Expiry is required"); return
            if not cvv:
                self._error.show_message("CVV is required"); return
            if not cvv.isdigit() or len(cvv) != 3:
                self._error.show_message("CVV must be 3 digits"); return
            self._error.clear_message()
            self._stack.setCurrentIndex(2)
            self._next_btn.setText("Next →")
        elif idx == 2:
            code = "".join(d.text().strip() for d in self._otp_digits)
            if len(code) != 6 or not code.isdigit():
                self._error.show_message("Please enter exactly 6 digits")
                return
            self._error.clear_message()
            self._build_summary()
            self._stack.setCurrentIndex(3)
            self._next_btn.setText("Confirm & Pay")
        elif idx == 3:
            self.accept()

    def selected_ids(self):
        return list(self._selected_ids)

    def _build_summary(self):
        total = 0
        lines = []
        for inv_id in self._selected_ids:
            inv = self._repo.get_invoice(inv_id)
            if inv:
                lines.append(f"{inv['invoice_number']}: {inv['description']} — ${inv['amount']:,.2f}")
                total += inv["amount"]
        lines.append("")
        lines.append(f"Total to charge: ${total:,.2f}")
        self._summary_label.setText("<br>".join(lines))

    def _go_back(self):
        idx = self._stack.currentIndex()
        if idx == 1:
            self._stack.setCurrentIndex(0)
            self._back_btn.hide()
            self._next_btn.setText("Next →")
        elif idx == 2:
            self._stack.setCurrentIndex(1)
            self._next_btn.setText("Next →")
        elif idx == 3:
            self._stack.setCurrentIndex(2)
            self._next_btn.setText("Next →")


class InvoicesPage(QWidget):
    def __init__(self, repo, user, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._user = user
        self._is_lawyer = user["role"] == "lawyer"
        self._build()
        self._load_table()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)

        header = QHBoxLayout()
        heading = QLabel("Invoices")
        heading.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        header.addWidget(heading)
        header.addStretch()
        if self._is_lawyer:
            new_btn = QPushButton("+ New Invoice")
            new_btn.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none;"
                                  f" border-radius: 4px; padding: 8px 18px; font-size: 13px; font-weight: bold; }}"
                                  f"QPushButton:hover {{ background: {STEEL}; }}")
            new_btn.clicked.connect(self._open_create)
            header.addWidget(new_btn)
        layout.addLayout(header)
        layout.addSpacing(12)

        self._build_table(layout)

        if not self._is_lawyer:
            pay_btn = QPushButton("Pay Invoices")
            pay_btn.setStyleSheet(f"QPushButton {{ background: {GREEN}; color: {WHITE}; border: none;"
                                  f" border-radius: 4px; padding: 10px 28px; font-size: 14px; font-weight: bold; }}"
                                  f"QPushButton:hover {{ background: #047857; }}")
            pay_btn.clicked.connect(self._open_payment)
            layout.addWidget(pay_btn, alignment=Qt.AlignRight)

    def _build_table(self, layout):
        cols = ["Invoice #", "Description", "Case", "Client" if self._is_lawyer else "Lawyer",
                "Amount", "Status", "Due Date"]
        self._table = QTableWidget()
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        h = self._table.horizontalHeader()
        h.setStretchLastSection(True)
        h.setSectionResizeMode(QHeaderView.Stretch)
        self._table.setStyleSheet(f"""
            QTableWidget {{ background: {WHITE}; border: 1px solid {BORDER}; border-radius: 4px;
                            gridline-color: {BORDER}; font-size: 13px; }}
            QTableWidget::item {{ padding: 6px 8px; color: {TEXT_DARK}; }}
            QHeaderView::section {{ background: {NAVY}; color: {WHITE}; padding: 8px;
                                    font-weight: bold; border: none; font-size: 12px; }}
            QTableWidget::item:alternate {{ background: #F8F9FB; }}
        """)
        layout.addWidget(self._table)

    def _load_table(self):
        invoices = (self._repo.get_invoices_for_lawyer(self._user["user_id"])
                    if self._is_lawyer
                    else self._repo.get_invoices_for_client(self._user["user_id"]))
        self._table.setRowCount(len(invoices))
        for row, inv in enumerate(invoices):
            self._table.setItem(row, 0, QTableWidgetItem(inv["invoice_number"]))
            self._table.setItem(row, 1, QTableWidgetItem(inv["description"]))
            case = self._repo.get_case(inv.get("case_id", ""))
            self._table.setItem(row, 2, QTableWidgetItem(case["case_number"] if case else "—"))
            pid = inv["client_id"] if self._is_lawyer else inv["lawyer_id"]
            person = self._repo.get_user(pid)
            pn = f"{person['first_name']} {person['last_name']}" if person else "—"
            self._table.setItem(row, 3, QTableWidgetItem(pn))
            self._table.setItem(row, 4, QTableWidgetItem(f"${inv['amount']:,.2f}"))
            self._table.setCellWidget(row, 5, _status_badge(inv["status"]))
            self._table.setItem(row, 6, QTableWidgetItem(inv.get("due_date", "")))

    def _open_create(self):
        dlg = InvoiceFormDialog(self._repo, self._user, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.invoice_data()
        data["lawyer_id"] = self._user["user_id"]
        inv = self._repo.create_invoice(data)
        client = self._repo.get_user(data["client_id"])
        cn = f"{client['first_name']} {client['last_name']}" if client else "a client"
        self._repo.create_notification({
            "user_id": data["client_id"],
            "title": "Invoice Created",
            "message": f"New invoice {inv['invoice_number']} for ${inv['amount']:,.2f} "
                       f"created by {cn}.",
            "notification_type": "invoice_created",
            "reference_id": inv["invoice_id"],
        })
        self._load_table()

    def _open_payment(self):
        dlg = PaymentDialog(self._repo, self._user["user_id"], parent=self)
        if dlg.exec() == QDialog.Accepted:
            for inv_id in dlg.selected_ids():
                self._repo.update_invoice(inv_id, status="Paid")
                inv = self._repo.get_invoice(inv_id)
                if inv:
                    self._repo.create_notification({
                        "user_id": inv["lawyer_id"],
                        "title": "Invoice Paid",
                        "message": f"Invoice {inv['invoice_number']} for ${inv['amount']:,.2f} has been paid.",
                        "notification_type": "invoice_paid",
                        "reference_id": inv_id,
                    })
            QMessageBox.information(self, "Payment Successful",
                                    "Your payment has been processed successfully.")
        self._load_table()


class PlaceholderPage(QWidget):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self._title = title
        self.setStyleSheet(f"background: {WHITE};")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        heading = QLabel(title)
        heading.setAlignment(Qt.AlignCenter)
        heading.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {TEXT_DARK};"
                              f" border: none; margin-bottom: 8px;")
        desc = QLabel(message)
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size: 14px; color: {TEXT_GRAY}; border: none;")
        layout.addWidget(heading)
        layout.addWidget(desc)


# ═══════════════════════════════════════════════════════════════════════════
# Main Window
# ═══════════════════════════════════════════════════════════════════════════

class MainWindow(QWidget):
    logout_requested = Signal()

    def __init__(self, repo, user):
        super().__init__()
        self._repo = repo
        self._user = user
        self.setWindowTitle("Engaz — Legal Management System")
        self.resize(1100, 720)
        self.setMinimumSize(860, 560)
        self._setup_ui()
        self._center_on_screen()

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sidebar = Sidebar(self._user["role"])
        self._sidebar.page_selected.connect(self._on_sidebar_navigate)
        self._sidebar.reset_requested.connect(self._handle_reset)
        root.addWidget(self._sidebar)

        main_area = QVBoxLayout()
        main_area.setContentsMargins(0, 0, 0, 0)
        main_area.setSpacing(0)

        self._header = HeaderBar(self._repo, self._user, self._navigate_to_page)
        self._header.sidebar_toggle_requested.connect(self._sidebar.toggle)
        main_area.addWidget(self._header)

        self._pages = QStackedWidget()
        if self._user["role"] == "stakeholder":
            from stakeholder_dashboard import StakeholderDashboardPage
            self._pages.addWidget(StakeholderDashboardPage(self._repo, self._user))
        else:
            self._pages.addWidget(DashboardPage(self._repo, self._user))
            dashboard = self._pages.widget(PAGE_DASHBOARD)
            dashboard.appointment_clicked.connect(self._on_appointment_clicked)
            self._pages.addWidget(Casepagemain(self._repo, self._user))
            self._pages.addWidget(CalendarPage(self._repo, self._user))
            self._pages.addWidget(InvoicesPage(self._repo, self._user))
            from messaging import MessagingPage
            self._pages.addWidget(MessagingPage(self._repo, self._user))
            if self._user["role"] == "lawyer":
                from lawyer_reports import LawyerReportsPage
                self._pages.addWidget(LawyerReportsPage(self._repo, self._user))
                from references import LawLibraryPage
                self._pages.addWidget(LawLibraryPage(self._repo, self._user))
            else:
                self._pages.addWidget(PlaceholderPage("Reports", "Reports are only available for lawyers."))
                self._pages.addWidget(PlaceholderPage("References", "References are only available for lawyers."))
        main_area.addWidget(self._pages)

        root.addLayout(main_area)

    def _on_sidebar_navigate(self, page):
        if page == -1:
            self.logout_requested.emit()
        else:
            self._navigate_to_page(page)

    def _navigate_to_page(self, page):
        if self._user["role"] == "stakeholder":
            page = 0
        self._pages.setCurrentIndex(page)
        page_widget = self._pages.widget(page)
        if hasattr(page_widget, "refresh"):
            page_widget.refresh()
        self._header.refresh_badge()

    def _on_appointment_clicked(self, date_str):
        cal_page = self._pages.widget(PAGE_CALENDAR)
        if cal_page and hasattr(cal_page, "navigate_to_date"):
            self._pages.setCurrentIndex(PAGE_CALENDAR)
            cal_page.navigate_to_date(date_str)
            self._header.refresh_badge()

    def _handle_reset(self):
        self._repo.reset_to_defaults()
        self.logout_requested.emit()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())


# ═══════════════════════════════════════════════════════════════════════════
# Application Entry Point
# ═══════════════════════════════════════════════════════════════════════════

class OTPDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Verification")
        self.resize(380, 200)
        self.setStyleSheet(f"background: {WHITE};")
        self._digits = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)

        lbl = QLabel("Enter the 6-digit verification code")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        layout.addWidget(lbl)

        sub = QLabel("A code was sent to your device")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"font-size: 12px; color: {TEXT_GRAY}; border: none;")
        layout.addWidget(sub)

        otp_row = QHBoxLayout()
        otp_row.setSpacing(8)
        otp_row.setAlignment(Qt.AlignCenter)
        for i in range(6):
            field = QLineEdit()
            field.setFixedSize(44, 48)
            field.setMaxLength(1)
            field.setAlignment(Qt.AlignCenter)
            field.setStyleSheet(f"""
                QLineEdit {{ font-size: 22px; font-weight: bold; color: {TEXT_DARK};
                             border: 2px solid {BORDER}; border-radius: 6px;
                             background: {WHITE}; padding: 0px; }}
                QLineEdit:focus {{ border-color: {STEEL}; }}
            """)
            field.textChanged.connect(lambda txt, idx=i: self._on_digit_changed(idx, txt))
            self._digits.append(field)
            otp_row.addWidget(field)
        layout.addLayout(otp_row)

        self._error = QLabel()
        self._error.setStyleSheet(f"color: {RED}; font-size: 11px; border: none;")
        self._error.setAlignment(Qt.AlignCenter)
        self._error.hide()
        layout.addWidget(self._error)

        verify_btn = QPushButton("Verify")
        verify_btn.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none;"
                                 f" border-radius: 6px; padding: 10px; font-size: 14px; font-weight: bold; }}"
                                 f"QPushButton:hover {{ background: {STEEL}; }}")
        verify_btn.clicked.connect(self._verify)
        layout.addWidget(verify_btn)

        self._digits[0].setFocus()

    def _on_digit_changed(self, idx, text):
        if text and idx < 5:
            self._digits[idx + 1].setFocus()

    def _verify(self):
        code = "".join(d.text().strip() for d in self._digits)
        if len(code) != 6 or not code.isdigit():
            self._error.setText("Please enter exactly 6 digits")
            self._error.show()
            return
        self._error.hide()
        self.accept()


class EngazApp:
    def __init__(self):
        self._app = QApplication(sys.argv)
        self._app.setStyle("Fusion")
        palette = self._app.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(26, 26, 46))
        palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(250, 250, 250))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(26, 26, 46))
        palette.setColor(QPalette.ColorRole.Text, QColor(26, 26, 46))
        palette.setColor(QPalette.ColorRole.Button, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(26, 26, 46))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Link, QColor(27, 58, 92))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(27, 58, 92))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        self._app.setPalette(palette)
        self._app.setStyleSheet("""
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background: #1B3A5C;
            }
            QCalendarWidget QToolButton {
                color: #FFFFFF;
                background: transparent;
                font-size: 14px;
                font-weight: bold;
            }
            QCalendarWidget QMenu {
                background: #FFFFFF;
                color: #1A1A2E;
            }
            QCalendarWidget QSpinBox {
                color: #FFFFFF;
                background: #1B3A5C;
                font-size: 13px;
                font-weight: bold;
            }
            QCalendarWidget QAbstractItemView {
                color: #1A1A2E;
                background: #FFFFFF;
                selection-background-color: #1B3A5C;
                selection-color: #FFFFFF;
            }
            QCalendarWidget QWidget {
                color: #6B7280;
                font-weight: bold;
            }
        """)
        self._repo = DataRepository()
        self._login = None
        self._main = None

    def run(self):
        self._show_login()
        return self._app.exec()

    def _show_login(self):
        if self._main:
            self._main.close()
            self._main = None
        self._login = LoginScreen(self._repo)
        self._login.login_successful.connect(self._on_login_success)
        self._login.show()

    def _on_login_success(self, user):
        self._login.close()
        otp = OTPDialog()
        if otp.exec() != QDialog.Accepted:
            self._show_login()
            return
        self._main = MainWindow(self._repo, user)
        self._main.logout_requested.connect(self._show_login)
        self._main.show()


if __name__ == "__main__":
    engaz = EngazApp()
    sys.exit(engaz.run())
