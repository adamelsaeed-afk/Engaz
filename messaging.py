from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QScrollArea, QFrame, QDialog, QComboBox, QDialogButtonBox,
    QSizePolicy, QSplitter,
)
from PySide6.QtCore import Qt, Signal, QTimer

from engaz_constants import (
    NAVY, STEEL, WHITE, CARD_BG, TEXT_DARK, TEXT_GRAY,
    GREEN, AMBER, RED, BORDER, _format_time, clear_layout,
)

from invoicesystem import ArrowComboBox


class NewConversationDialog(QDialog):
    def __init__(self, repo, user, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._user = user
        self._is_lawyer = user["role"] == "lawyer"
        self.setWindowTitle("New Conversation")
        self.resize(420, 320)
        self._selected_partner_id = None
        self._selected_case_id = ""
        self._build()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        lbl = QLabel("Select a contact to message:")
        lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        layout.addWidget(lbl)

        self._contact_combo = ArrowComboBox()
        self._contact_combo.setStyleSheet(f"""
            QComboBox {{ padding: 6px 8px; border: 1px solid {BORDER}; border-radius: 4px;
                          font-size: 13px; color: {TEXT_DARK}; background: {WHITE}; }}
            QComboBox:focus {{ border-color: {STEEL}; }}
        """)
        layout.addWidget(self._contact_combo)

        case_lbl = QLabel("Link to case (optional):")
        case_lbl.setStyleSheet(f"font-size: 13px; color: {TEXT_GRAY}; border: none;")
        layout.addWidget(case_lbl)

        self._case_combo = ArrowComboBox()
        self._case_combo.setStyleSheet(f"""
            QComboBox {{ padding: 6px 8px; border: 1px solid {BORDER}; border-radius: 4px;
                          font-size: 13px; color: {TEXT_DARK}; background: {WHITE}; }}
            QComboBox:focus {{ border-color: {STEEL}; }}
        """)
        self._case_combo.addItem("(No case — direct message)", "")
        layout.addWidget(self._case_combo)

        layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.setStyleSheet(f"QPushButton {{ padding: 6px 16px; border-radius: 4px; font-size: 13px; }}")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._populate_contacts()

    def _populate_contacts(self):
        if self._is_lawyer:
            cases = self._repo.get_cases_for_lawyer(self._user["user_id"])
        else:
            cases = self._repo.get_cases_for_client(self._user["user_id"])
        seen = set()
        for case in cases:
            partner_id = case["client_id"] if self._is_lawyer else case["lawyer_id"]
            if partner_id not in seen:
                seen.add(partner_id)
                partner = self._repo.get_user(partner_id)
                if partner:
                    name = f"{partner['first_name']} {partner['last_name']}"
                    self._contact_combo.addItem(name, partner_id)
        if self._contact_combo.count() == 0:
            self._contact_combo.addItem("No contacts available", "")

        self._contact_combo.currentIndexChanged.connect(self._on_contact_changed)
        self._on_contact_changed(0)

    def _on_contact_changed(self, index):
        partner_id = self._contact_combo.currentData()
        self._case_combo.clear()
        self._case_combo.addItem("(No case — direct message)", "")
        if not partner_id:
            return
        if self._is_lawyer:
            cases = self._repo.get_cases_for_lawyer(self._user["user_id"])
            shared_cases = [c for c in cases if c["client_id"] == partner_id]
        else:
            cases = self._repo.get_cases_for_client(self._user["user_id"])
            shared_cases = [c for c in cases if c["lawyer_id"] == partner_id]
        for case in shared_cases:
            self._case_combo.addItem(f"{case['title']} (#{case['case_id'][:8]})", case["case_id"])

    def selected_partner_id(self):
        return self._contact_combo.currentData()

    def selected_case_id(self):
        return self._case_combo.currentData()


class MessageBubble(QFrame):
    def __init__(self, content, is_sender, timestamp, parent=None):
        super().__init__(parent)
        self._build(content, is_sender, timestamp)

    def _build(self, content, is_sender, timestamp):
        self.setStyleSheet("border: none; background: transparent;")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 4, 12, 4)

        bubble = QFrame()
        bubble_bg = NAVY if is_sender else "#F1F3F5"
        bubble_fg = WHITE if is_sender else TEXT_DARK
        bubble.setStyleSheet(f"""
            QFrame {{
                background: {bubble_bg};
                border-radius: 14px;
                border: none;
            }}
        """)
        bubble.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(14, 8, 14, 8)
        bubble_layout.setSpacing(2)

        text = QLabel(content)
        text.setWordWrap(True)
        text.setMaximumWidth(420)
        text.setStyleSheet(f"color: {bubble_fg}; font-size: 13px; border: none;")
        bubble_layout.addWidget(text)

        time_lbl = QLabel(_format_time(timestamp))
        time_lbl.setStyleSheet(f"color: {'rgba(255,255,255,0.6)' if is_sender else TEXT_GRAY};"
                               f" font-size: 10px; border: none;")
        time_lbl.setAlignment(Qt.AlignRight)
        bubble_layout.addWidget(time_lbl)

        if is_sender:
            outer.addStretch()
            outer.addWidget(bubble)
        else:
            outer.addWidget(bubble)
            outer.addStretch()


class MessageThreadWidget(QWidget):
    message_sent = Signal(str, str, str)

    def __init__(self, repo, user, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._user = user
        self._partner_id = None
        self._partner_name = ""
        self._case_id = ""
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._case_bar = QLabel()
        self._case_bar.setStyleSheet(f"background: {STEEL}; color: {WHITE}; padding: 6px 16px;"
                                     f" font-size: 12px; font-weight: bold; border: none;")
        self._case_bar.hide()
        layout.addWidget(self._case_bar)

        self._header_label = QLabel()
        self._header_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {TEXT_DARK};"
                                         f" padding: 12px 16px; border: none;"
                                         f" border-bottom: 1px solid {BORDER};")
        layout.addWidget(self._header_label)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(f"border: none; background: {WHITE};")
        self._msg_container = QWidget()
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(0, 0, 0, 0)
        self._msg_layout.setSpacing(2)
        self._msg_layout.addStretch()
        self._scroll.setWidget(self._msg_container)
        layout.addWidget(self._scroll, stretch=1)

        input_area = QFrame()
        input_area.setStyleSheet(f"background: {WHITE}; border-top: 1px solid {BORDER};")
        input_layout = QHBoxLayout(input_area)
        input_layout.setContentsMargins(12, 8, 12, 8)
        input_layout.setSpacing(8)

        self._input = QTextEdit()
        self._input.setPlaceholderText("Type a message...")
        self._input.setFixedHeight(50)
        self._input.setStyleSheet(f"padding: 6px; border: 1px solid {BORDER}; border-radius: 6px;"
                                  f" font-size: 13px; color: {TEXT_DARK}; background: {WHITE};")
        input_layout.addWidget(self._input, stretch=1)

        send_btn = QPushButton("Send")
        send_btn.setFixedHeight(36)
        send_btn.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none;"
                               f" border-radius: 6px; padding: 0 18px; font-size: 13px; font-weight: bold; }}"
                               f"QPushButton:hover {{ background: {STEEL}; }}")
        send_btn.clicked.connect(self._send)
        input_layout.addWidget(send_btn)

        layout.addWidget(input_area)

        self.show_placeholder()

    def show_placeholder(self):
        self._header_label.setText("Messages")
        self._case_bar.hide()
        self._partner_id = None
        self._partner_name = ""
        self._case_id = ""
        self._input.setEnabled(False)
        self._clear_messages()
        placeholder = QLabel("Select a conversation to start messaging")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 14px; border: none;")
        self._msg_layout.insertWidget(0, placeholder)

    def load_conversation(self, partner_id, partner_name, case_id=""):
        self._partner_id = partner_id
        self._partner_name = partner_name
        self._case_id = case_id
        self._header_label.setText(partner_name)
        self._input.setEnabled(True)
        self._input.clear()
        if case_id:
            case = self._repo.get_case(case_id)
            cn = case["case_number"] if case else ""
            ct = case["title"] if case else ""
            self._case_bar.setText(f"Case: {cn} — {ct}" if case else "")
            self._case_bar.show()
        else:
            self._case_bar.hide()
        self._repo.mark_messages_read(partner_id, self._user["user_id"])
        self._refresh_messages()

    def _refresh_messages(self):
        self._clear_messages()
        if not self._partner_id:
            return
        if self._case_id:
            messages = self._repo.get_messages_for_case(self._case_id, self._user["user_id"])
        else:
            messages = self._repo.get_messages_between(self._user["user_id"], self._partner_id)
        for msg in messages:
            is_sender = msg["sender_id"] == self._user["user_id"]
            self._msg_layout.addWidget(
                MessageBubble(msg["content"], is_sender, msg["created_at"])
            )
        self._msg_layout.addStretch()
        QTimer.singleShot(30, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        if not self.isVisible():
            return
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear_messages(self):
        clear_layout(self._msg_layout)

    def _send(self):
        content = self._input.toPlainText().strip()
        if not content or not self._partner_id:
            return
        self._input.clear()
        msg = self._repo.create_message({
            "sender_id": self._user["user_id"],
            "receiver_id": self._partner_id,
            "content": content,
            "case_id": self._case_id,
        })
        self._repo.create_notification({
            "user_id": self._partner_id,
            "title": "New Message",
            "message": f"{self._user['first_name']} sent you a message.",
            "notification_type": "message_received",
            "reference_id": msg["message_id"],
        })
        self._refresh_messages()
        self.message_sent.emit(self._partner_id, self._partner_name, content)

    def partner_id(self):
        return self._partner_id


class ConversationListWidget(QWidget):
    conversation_selected = Signal(str, str, str)

    def __init__(self, repo, user, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._user = user
        self._is_lawyer = user["role"] == "lawyer"
        self._selected_id = None
        self._build()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE}; border: none;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("Conversations")
        header.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT_DARK};"
                             f" padding: 12px 14px; border: none; border-bottom: 1px solid {BORDER};")
        layout.addWidget(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(f"border: none; background: {WHITE};")
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        self._scroll.setWidget(self._list_container)
        layout.addWidget(self._scroll, stretch=1)

    def refresh(self):
        clear_layout(self._list_layout)
        conversations = self._repo.get_conversations_for_user(self._user["user_id"])
        if self._is_lawyer:
            overdue = self._repo.get_overdue_reply_threads(self._user["user_id"])
            overdue_ids = {o["partner_id"] for o in overdue}
            for o in overdue:
                exists = any(c["partner_id"] == o["partner_id"] for c in conversations)
                if not exists:
                    conversations.append({
                        "partner_id": o["partner_id"],
                        "last_message": "No replies yet",
                        "last_at": o["last_at"],
                        "last_sender_id": o["partner_id"],
                        "case_id": "",
                        "unread_count": 0,
                    })
        else:
            overdue_ids = set()
        if not conversations:
            empty = QLabel("No conversations yet")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 12px; padding: 20px; border: none;")
            self._list_layout.insertWidget(0, empty)
        else:
            for conv in conversations:
                pid = conv["partner_id"]
                partner = self._repo.get_user(pid)
                pname = f"{partner['first_name']} {partner['last_name']}" if partner else "Unknown"
                is_overdue = pid in overdue_ids
                row = self._make_conv_row(pname, conv, is_overdue)
                self._list_layout.insertWidget(self._list_layout.count() - 1, row)
        self._list_layout.addStretch()

    def _make_conv_row(self, pname, conv, is_overdue):
        frame = QFrame()
        frame.setCursor(Qt.PointingHandCursor)
        frame.setFixedHeight(64)
        selected = conv["partner_id"] == self._selected_id
        bg = "#EBF0F5" if selected else WHITE
        frame.setStyleSheet(f"QFrame {{ background: {bg}; border: none;"
                            f" border-bottom: 1px solid {BORDER}; }}"
                            f"QFrame:hover {{ background: {'#DDE4EB' if selected else '#F4F6F8'}; }}")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        info = QVBoxLayout()
        info.setSpacing(2)
        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        name_lbl = QLabel(pname)
        name_lbl.setStyleSheet(f"font-weight: bold; color: {TEXT_DARK}; font-size: 13px; border: none;")
        name_row.addWidget(name_lbl)
        if is_overdue:
            warn = QLabel("\u26a0")
            warn.setStyleSheet(f"color: {AMBER}; font-size: 14px; border: none;")
            name_row.addWidget(warn)
        name_row.addStretch()
        info.addLayout(name_row)

        preview = conv.get("last_message", "")
        if len(preview) > 40:
            preview = preview[:40] + "..."
        preview_lbl = QLabel(preview)
        preview_lbl.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 11px; border: none;")
        info.addWidget(preview_lbl)

        layout.addLayout(info, stretch=1)

        right_col = QVBoxLayout()
        right_col.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        time_lbl = QLabel(_format_time(conv.get("last_at", "")))
        time_lbl.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 10px; border: none;")
        time_lbl.setAlignment(Qt.AlignRight)
        right_col.addWidget(time_lbl)

        unread = conv.get("unread_count", 0)
        if unread > 0:
            badge = QLabel(str(unread))
            badge.setAlignment(Qt.AlignCenter)
            badge.setFixedSize(20, 20)
            badge.setStyleSheet(f"background: {STEEL}; color: {WHITE}; font-size: 10px;"
                                f" font-weight: bold; border-radius: 10px; border: none;")
            right_col.addWidget(badge, alignment=Qt.AlignRight)

        layout.addLayout(right_col)

        pid = conv["partner_id"]
        cid = conv.get("case_id", "")
        frame.mousePressEvent = lambda e, p=pid, n=pname, c=cid: self._select(p, n, c)
        return frame

    def _select(self, partner_id, partner_name, case_id):
        self._selected_id = partner_id
        self.conversation_selected.emit(partner_id, partner_name, case_id)


class MessagingPage(QWidget):
    def __init__(self, repo, user, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._user = user
        self.setStyleSheet(f"background: {WHITE};")
        self._build()

    def _build(self):
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(5)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background: #E5E7EB;
            }
            QSplitter::handle:hover {
                background: #94A3B8;
            }
        """)

        left_panel = QFrame()
        left_panel.setMinimumWidth(200)
        left_panel.setMaximumWidth(450)
        left_panel.setStyleSheet(f"background: {WHITE}; border-right: 1px solid {BORDER};")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self._conv_list = ConversationListWidget(self._repo, self._user)
        self._conv_list.conversation_selected.connect(self._on_conversation_selected)
        left_layout.addWidget(self._conv_list, stretch=1)

        self._fab_btn = QPushButton("+")
        self._fab_btn.setFixedSize(36, 36)
        self._fab_btn.setCursor(Qt.PointingHandCursor)
        self._fab_btn.setStyleSheet(f"""
            QPushButton {{
                background: {NAVY}; color: {WHITE};
                border: none; border-radius: 18px;
                font-size: 20px; font-weight: bold;
                padding: 0; text-align: center;
            }}
            QPushButton:hover {{
                background: {STEEL};
            }}
        """)
        self._fab_btn.setToolTip("New Conversation")
        self._fab_btn.setParent(left_panel)
        self._fab_btn.clicked.connect(self._open_new_conversation)
        self._fab_btn.raise_()

        left_panel.resizeEvent = self._reposition_fab

        splitter.addWidget(left_panel)

        self._thread = MessageThreadWidget(self._repo, self._user)
        self._thread.message_sent.connect(self._on_message_sent)
        self._thread.setMinimumWidth(300)
        splitter.addWidget(self._thread)

        splitter.setSizes([290, 700])

        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addWidget(splitter)

    def _reposition_fab(self, event):
        QFrame.resizeEvent(self._fab_btn.parent(), event)
        parent = self._fab_btn.parent()
        self._fab_btn.move(parent.width() - 46, parent.height() - 46)

    def refresh(self):
        self._conv_list.refresh()
        partner_id = self._thread.partner_id()
        if partner_id:
            self._repo.mark_messages_read(partner_id, self._user["user_id"])
            self._thread._refresh_messages()

    def _on_conversation_selected(self, partner_id, partner_name, case_id):
        self._thread.load_conversation(partner_id, partner_name, case_id)
        self._conv_list.refresh()

    def _on_message_sent(self, partner_id, partner_name, content):
        self._conv_list.refresh()

    def _open_new_conversation(self):
        dlg = NewConversationDialog(self._repo, self._user, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        partner_id = dlg.selected_partner_id()
        if not partner_id:
            return
        case_id = dlg.selected_case_id()
        partner = self._repo.get_user(partner_id)
        pname = f"{partner['first_name']} {partner['last_name']}" if partner else "Unknown"
        self._thread.load_conversation(partner_id, pname, case_id)
        self._conv_list.refresh()
