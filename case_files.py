import os
import shutil

CASE_FILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "case_files")


def _ensure_case_files_dir():
    if not os.path.exists(CASE_FILES_DIR):
        os.makedirs(CASE_FILES_DIR)

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialog, QFileDialog, QFrame, QScrollArea, QGridLayout, QSizePolicy,
    QMenu, QMessageBox, QCheckBox, QLineEdit, QTextEdit,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt, Signal, QUrl, QDate
from PySide6.QtGui import QDesktopServices

from engaz_constants import (
    NAVY, STEEL, WHITE, CARD_BG, TEXT_DARK, TEXT_GRAY,
    GREEN, AMBER, RED, BORDER, _status_badge, _client_display_name,
    ArrowComboBox, ArrowDateEdit, GLOBAL_QSS, BTN_PRIMARY_HOVER,
    BTN_SECONDARY_HOVER, BTN_DESTRUCTIVE_HOVER, create_required_label,
)


class AddFileDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add File to Case")
        self.resize(500, 120)
        self._file_path = ""
        self._build()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        lbl = QLabel("Select a file to add to the case:")
        lbl.setStyleSheet(f"font-size: 13px; color: {TEXT_DARK}; border: none;")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        picker_row = QHBoxLayout()
        self._path_display = QLabel("No file selected")
        self._path_display.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 12px; border: 1px solid {BORDER};"
                                         f" padding: 6px 8px; border-radius: 4px; background: {CARD_BG};")
        self._path_display.setWordWrap(True)
        picker_row.addWidget(self._path_display, stretch=1)

        browse_btn = QPushButton("Browse...")
        browse_btn.setStyleSheet(f"QPushButton {{ background: {STEEL}; color: {WHITE}; border: none;"
                                 f" border-radius: 4px; padding: 6px 14px; font-size: 12px; font-weight: bold; }}"
                                 f"QPushButton:hover {{ background: {NAVY}; }}")
        browse_btn.clicked.connect(self._browse)
        picker_row.addWidget(browse_btn)
        layout.addLayout(picker_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {TEXT_GRAY}; border: none;"
                                 f" font-size: 13px; padding: 6px 12px; }}")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        add_btn = QPushButton("Add File")
        add_btn.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none;"
                              f" border-radius: 4px; padding: 6px 16px; font-size: 13px; font-weight: bold; }}"
                              f"QPushButton:hover {{ background: {STEEL}; }}")
        add_btn.clicked.connect(self._add)
        btn_row.addWidget(add_btn)
        layout.addLayout(btn_row)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File", "", "All Files (*)")
        if path:
            self._file_path = path
            self._path_display.setText(path)

    def _add(self):
        if not self._file_path:
            return
        self.accept()

    def file_path(self):
        return self._file_path

    def file_name(self):
        return os.path.basename(self._file_path)


class CaseFileListWidget(QWidget):
    files_changed = Signal()

    def __init__(self, repo, case_id, viewer_user_id, viewer_role, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._case_id = case_id
        self._viewer_user_id = viewer_user_id
        self._viewer_role = viewer_role
        self._is_lawyer = viewer_role == "lawyer"
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Case Files")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        header.addWidget(title)
        header.addStretch()
        add_btn = QPushButton("+ Add File")
        add_btn.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none;"
                              f" border-radius: 4px; padding: 6px 14px; font-size: 12px; font-weight: bold; }}"
                              f"QPushButton:hover {{ background: {STEEL}; }}")
        add_btn.clicked.connect(self._add_file)
        header.addWidget(add_btn)
        layout.addLayout(header)

        cols = ["File Name", "Added By", "Date Added"]
        if self._is_lawyer:
            cols.append("Shared")
        cols.append("Actions")
        self._table = QTableWidget()
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        h = self._table.horizontalHeader()
        h.setStretchLastSection(True)
        h.setSectionResizeMode(QHeaderView.Stretch)
        self._table.setStyleSheet(f"""
            QTableWidget {{ background: {WHITE}; border: 1px solid {BORDER}; border-radius: 4px;
                            gridline-color: {BORDER}; font-size: 12px; }}
            QTableWidget::item {{ padding: 4px 8px; color: {TEXT_DARK}; }}
            QHeaderView::section {{ background: {NAVY}; color: {WHITE}; padding: 6px;
                                    font-weight: bold; border: none; font-size: 11px; }}
            QTableWidget::item:alternate {{ background: #F8F9FB; }}
        """)
        layout.addWidget(self._table)

        if not self._is_lawyer:
            note = QLabel("Files shared by your lawyer are marked accordingly.")
            note.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 11px; border: none; font-style: italic;")
            layout.addWidget(note)

    def _load(self):
        files = self._repo.get_files_for_case(self._case_id, self._viewer_user_id, self._viewer_role)
        col_count = 4 if self._is_lawyer else 3
        self._table.setRowCount(len(files))
        for row, f in enumerate(files):
            self._table.setItem(row, 0, QTableWidgetItem(f["file_name"]))
            adder = self._repo.get_user(f["added_by"])
            adder_name = f"{adder['first_name']} {adder['last_name']}" if adder else "—"
            self._table.setItem(row, 1, QTableWidgetItem(adder_name))
            self._table.setItem(row, 2, QTableWidgetItem(f["added_at"][:10]))

            col_offset = 0

            if self._is_lawyer:
                shared = "Yes" if f["shared_with_client"] else "No"
                shared_item = QTableWidgetItem(shared)
                shared_item.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(row, 3, shared_item)
                col_offset = 1

            kebab_btn = QPushButton("\u22ee")
            kebab_btn.setFixedSize(28, 28)
            kebab_btn.setCursor(Qt.PointingHandCursor)
            kebab_btn.setStyleSheet("""
                QPushButton {
                    background: transparent; border: none;
                    font-size: 18px; font-weight: bold; color: #6B7280;
                }
                QPushButton:hover { background: #F3F4F6; border-radius: 4px; }
            """)

            menu = QMenu(kebab_btn)
            menu.setStyleSheet("""
                QMenu {
                    background: white; border: 1px solid #E5E7EB; border-radius: 6px;
                    padding: 4px 0;
                }
                QMenu::item { padding: 6px 16px; font-size: 12px; }
                QMenu::item:selected { background: #F3F4F6; }
            """)

            open_action = menu.addAction("Open")
            open_action.triggered.connect(lambda chk=False, fp=f["file_path"]: self._open_file(fp))

            if self._is_lawyer:
                label = "Unshare" if f["shared_with_client"] else "Share with Client"
                share_action = menu.addAction(label)
                share_action.triggered.connect(lambda chk=False, fid=f["file_id"]: self._toggle_share(fid))

            remove_action = menu.addAction("Remove")
            remove_action.triggered.connect(lambda chk=False, fid=f["file_id"]: self._remove_file(fid))

            kebab_btn.clicked.connect(
                lambda chk=False, b=kebab_btn, m=menu:
                    m.exec(b.mapToGlobal(b.rect().bottomLeft()))
            )

            wrapper = QWidget()
            wrapper.setStyleSheet("border: none; background: transparent;")
            wrapper_layout = QHBoxLayout(wrapper)
            wrapper_layout.setContentsMargins(0, 0, 0, 0)
            wrapper_layout.addStretch()
            wrapper_layout.addWidget(kebab_btn)
            self._table.setCellWidget(row, 3 + col_offset, wrapper)

    def _add_file(self):
        dlg = AddFileDialog(parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        _ensure_case_files_dir()
        file_path = dlg.file_path()
        file_name = dlg.file_name()
        file_id = self._repo._next_id("case_files", "file")
        ext = os.path.splitext(file_name)[1]
        safe_name = f"{file_id}{ext}"
        try:
            shutil.copy2(file_path, os.path.join(CASE_FILES_DIR, safe_name))
        except OSError:
            QMessageBox.warning(self, "Error", "Could not copy the file.")
            return
        self._repo.add_case_file({
            "case_id": self._case_id,
            "added_by": self._viewer_user_id,
            "file_name": dlg.file_name(),
            "file_path": safe_name,
            "shared_with_client": False,
        })
        self._load()
        self.files_changed.emit()

    def _toggle_share(self, file_id):
        updated = self._repo.toggle_file_sharing(file_id)
        if updated and updated.get("shared_with_client"):
            case = self._repo.get_case(self._case_id)
            if case:
                self._repo.create_notification({
                    "user_id": case["client_id"],
                    "title": "New Case Attachment",
                    "message": f"New attachment added to case: {case['title']}",
                    "notification_type": "case_attachment_added",
                    "reference_id": self._case_id,
                })
        self._load()
        self.files_changed.emit()

    def _remove_file(self, file_id):
        reply = QMessageBox.question(
            self, "Confirm Removal",
            "Are you sure you want to remove this file? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._repo.delete_case_file(file_id)
        self._load()
        self.files_changed.emit()

    def _open_file(self, file_path):
        resolved = os.path.join(CASE_FILES_DIR, file_path)
        if os.path.exists(resolved):
            QDesktopServices.openUrl(QUrl.fromLocalFile(resolved))
        else:
            QMessageBox.warning(self, "File Not Found",
                                f"The file could not be found at:\n{resolved}")


class TaskFormDialog(QDialog):
    def __init__(self, repo, case_id, user_id, task=None, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._case_id = case_id
        self._user_id = user_id
        self._task = task
        self._is_edit = task is not None
        self.setWindowTitle("Edit Task" if self._is_edit else "New Task")
        self.resize(420, 300)
        self._build()
        if self._is_edit:
            self._fill_form()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        row = QHBoxLayout()
        row.addWidget(QLabel(create_required_label("Title:")))
        self._title = QLineEdit()
        self._title.setPlaceholderText("Please enter a task title")
        self._title.setStyleSheet(GLOBAL_QSS)
        row.addWidget(self._title, stretch=1)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Assigned To:"))
        self._assigned = ArrowComboBox(placeholder="Select assignee...")
        self._assigned.setStyleSheet(GLOBAL_QSS)
        case = self._repo.get_case(self._case_id)
        if case:
            client = self._repo.get_user(case["client_id"])
            lawyer = self._repo.get_user(case["lawyer_id"])
            if lawyer:
                self._assigned.addItem(f"{lawyer['first_name']} {lawyer['last_name']} (Lawyer)", lawyer["user_id"])
            if client:
                self._assigned.addItem(f"{client['first_name']} {client['last_name']} (Client)", client["user_id"])
        row.addWidget(self._assigned, stretch=1)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Due Date:"))
        self._due_date = ArrowDateEdit()
        self._due_date.setDate(QDate.currentDate())
        self._due_date.setStyleSheet(GLOBAL_QSS)
        row.addWidget(self._due_date, stretch=1)
        layout.addLayout(row)

        layout.addWidget(QLabel("Description:"))
        self._desc = QTextEdit()
        self._desc.setMaximumHeight(60)
        self._desc.setStyleSheet(GLOBAL_QSS)
        layout.addWidget(self._desc)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._try_save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _fill_form(self):
        self._title.setText(self._task.get("title", ""))
        self._desc.setText(self._task.get("description", ""))
        idx = self._assigned.findData(self._task.get("assigned_to", ""))
        if idx >= 0:
            self._assigned.setCurrentIndex(idx)
        if self._task.get("due_date"):
            dt = QDate.fromString(self._task["due_date"], "yyyy-MM-dd")
            if dt.isValid():
                self._due_date.setDate(dt)

    def _try_save(self):
        if not self._title.text().strip():
            QMessageBox.warning(self, "Validation", "Title is required.")
            return
        self.accept()

    def task_data(self):
        return {
            "title": self._title.text().strip(),
            "description": self._desc.toPlainText().strip(),
            "assigned_to": self._assigned.currentData() or "",
            "due_date": self._due_date.date().toString("yyyy-MM-dd"),
            "is_completed": self._task.get("is_completed", False) if self._task else False,
        }


class CaseTasksWidget(QWidget):
    tasks_changed = Signal()

    def __init__(self, repo, case_id, viewer_user_id, viewer_role, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._case_id = case_id
        self._viewer_user_id = viewer_user_id
        self._is_lawyer = viewer_role == "lawyer"
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Case Tasks")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        header.addWidget(title)
        header.addStretch()
        add_btn = QPushButton("+ Add Task")
        add_btn.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none;"
                              f" border-radius: 4px; padding: 6px 14px; font-size: 12px; font-weight: bold; }}"
                              f"QPushButton:hover {{ background: {STEEL}; }}")
        add_btn.clicked.connect(self._add_task)
        header.addWidget(add_btn)
        layout.addLayout(header)

        self._list = QVBoxLayout()
        self._list.setSpacing(4)
        layout.addLayout(self._list)
        layout.addStretch()

    def _load(self):
        clear_layout_inner(self._list)
        tasks = self._repo.get_tasks_for_case(self._case_id)
        if not tasks:
            empty = QLabel("  No tasks yet.")
            empty.setStyleSheet(f"color: {TEXT_GRAY}; padding: 8px; border: none; font-style: italic;")
            self._list.addWidget(empty)
            return
        for task in tasks:
            self._list.addWidget(self._task_row(task))

    def _task_row(self, task):
        row = QWidget()
        row.setStyleSheet(f"background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 4px;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(8, 6, 8, 6)

        cb = QCheckBox()
        cb.setChecked(task["is_completed"])
        cb.toggled.connect(lambda checked, t=task: self._toggle(t, checked))
        rl.addWidget(cb)

        info = QVBoxLayout()
        tl = QLabel(task["title"])
        tl.setStyleSheet(f"font-weight: bold; color: {TEXT_DARK}; font-size: 12px; border: none; background: transparent;")
        if task["is_completed"]:
            tl.setStyleSheet(f"font-weight: bold; color: {TEXT_GRAY}; font-size: 12px; text-decoration: line-through; border: none; background: transparent;")
        info.addWidget(tl)
        detail = []
        if task.get("assigned_to"):
            assignee = self._repo.get_user(task["assigned_to"])
            if assignee:
                detail.append(f"{assignee['first_name']} {assignee['last_name']}")
        if task.get("due_date"):
            detail.append(task["due_date"])
        if detail:
            dl = QLabel("  |  ".join(detail))
            dl.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 11px; border: none; background: transparent;")
            info.addWidget(dl)
        rl.addLayout(info, stretch=1)

        del_btn = QPushButton("\u2715")
        del_btn.setFixedSize(24, 24)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet("QPushButton { background: transparent; border: none; color: #DC2626; font-size: 14px; }"
                              "QPushButton:hover { background: #FEE2E2; border-radius: 4px; }")
        del_btn.clicked.connect(lambda: self._delete(task["task_id"]))
        rl.addWidget(del_btn)

        return row

    def _add_task(self):
        dlg = TaskFormDialog(self._repo, self._case_id, self._viewer_user_id, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.task_data()
        data["case_id"] = self._case_id
        self._repo.create_task(data)
        self._load()
        self.tasks_changed.emit()

    def _toggle(self, task, checked):
        self._repo.update_task(task["task_id"], is_completed=checked)
        self._load()
        self.tasks_changed.emit()

    def _delete(self, task_id):
        reply = QMessageBox.question(
            self, "Delete Task", "Remove this task?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._repo.delete_task(task_id)
            self._load()
            self.tasks_changed.emit()


class TimelineFormDialog(QDialog):
    EVENTS = ["Hearing", "Deadline", "Filing", "Milestone"]

    def __init__(self, repo, case_id, timeline=None, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._case_id = case_id
        self._timeline = timeline
        self._is_edit = timeline is not None
        self.setWindowTitle("Edit Timeline Event" if self._is_edit else "New Timeline Event")
        self.resize(420, 300)
        self._build()
        if self._is_edit:
            self._fill_form()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        row = QHBoxLayout()
        row.addWidget(QLabel("Event Type:"))
        self._event_type = ArrowComboBox(placeholder="Select event type...")
        self._event_type.addItems(self.EVENTS)
        self._event_type.setStyleSheet(GLOBAL_QSS)
        row.addWidget(self._event_type, stretch=1)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel(create_required_label("Title:")))
        self._title = QLineEdit()
        self._title.setPlaceholderText("Please enter an event title")
        self._title.setStyleSheet(GLOBAL_QSS)
        row.addWidget(self._title, stretch=1)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Event Date:"))
        self._event_date = ArrowDateEdit()
        self._event_date.setDate(QDate.currentDate())
        self._event_date.setStyleSheet(GLOBAL_QSS)
        row.addWidget(self._event_date, stretch=1)
        layout.addLayout(row)

        layout.addWidget(QLabel("Description:"))
        self._desc = QTextEdit()
        self._desc.setMaximumHeight(60)
        self._desc.setStyleSheet(GLOBAL_QSS)
        layout.addWidget(self._desc)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._try_save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _fill_form(self):
        self._title.setText(self._timeline.get("title", ""))
        self._desc.setText(self._timeline.get("description", ""))
        idx = self._event_type.findText(self._timeline.get("event_type", "Milestone"))
        if idx >= 0:
            self._event_type.setCurrentIndex(idx)
        if self._timeline.get("event_date"):
            dt = QDate.fromString(self._timeline["event_date"], "yyyy-MM-dd")
            if dt.isValid():
                self._event_date.setDate(dt)

    def _try_save(self):
        if not self._title.text().strip():
            QMessageBox.warning(self, "Validation", "Title is required.")
            return
        self.accept()

    def timeline_data(self):
        return {
            "event_type": self._event_type.currentText(),
            "title": self._title.text().strip(),
            "description": self._desc.toPlainText().strip(),
            "event_date": self._event_date.date().toString("yyyy-MM-dd"),
            "is_completed": self._timeline.get("is_completed", False) if self._timeline else False,
        }


class CaseTimelineWidget(QWidget):
    timeline_changed = Signal()

    def __init__(self, repo, case_id, viewer_user_id, viewer_role, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._case_id = case_id
        self._viewer_user_id = viewer_user_id
        self._is_lawyer = viewer_role == "lawyer"
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Case Timeline")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        header.addWidget(title)
        header.addStretch()
        add_btn = QPushButton("+ Add Event")
        add_btn.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none;"
                              f" border-radius: 4px; padding: 6px 14px; font-size: 12px; font-weight: bold; }}"
                              f"QPushButton:hover {{ background: {STEEL}; }}")
        add_btn.clicked.connect(self._add_timeline)
        header.addWidget(add_btn)
        layout.addLayout(header)

        self._list = QVBoxLayout()
        self._list.setSpacing(4)
        layout.addLayout(self._list)
        layout.addStretch()

    def _load(self):
        clear_layout_inner(self._list)
        items = self._repo.get_timelines_for_case(self._case_id)
        if not items:
            empty = QLabel("  No timeline events yet.")
            empty.setStyleSheet(f"color: {TEXT_GRAY}; padding: 8px; border: none; font-style: italic;")
            self._list.addWidget(empty)
            return
        for item in items:
            self._list.addWidget(self._timeline_row(item))

    def _timeline_row(self, item):
        row = QWidget()
        row.setStyleSheet(f"background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 4px;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(8, 6, 8, 6)

        cb = QCheckBox()
        cb.setChecked(item["is_completed"])
        cb.toggled.connect(lambda checked, t=item: self._toggle(t, checked))
        rl.addWidget(cb)

        info = QVBoxLayout()
        et = QLabel(item.get("event_type", "Milestone"))
        badge_colors = {
            "Hearing": STEEL, "Deadline": RED, "Filing": AMBER, "Milestone": NAVY,
        }
        color = badge_colors.get(item.get("event_type", ""), TEXT_GRAY)
        et.setStyleSheet(f"font-size: 10px; font-weight: bold; color: {color}; border: none; background: transparent;")
        info.addWidget(et)

        tl = QLabel(item["title"])
        tl.setStyleSheet(f"font-weight: bold; color: {TEXT_DARK}; font-size: 12px; border: none; background: transparent;")
        if item["is_completed"]:
            tl.setStyleSheet(f"font-weight: bold; color: {TEXT_GRAY}; font-size: 12px; text-decoration: line-through; border: none; background: transparent;")
        info.addWidget(tl)

        detail = []
        if item.get("event_date"):
            detail.append(item["event_date"])
        if item.get("description"):
            detail.append(item["description"])
        if detail:
            dl = QLabel("  |  ".join(detail))
            dl.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 11px; border: none; background: transparent;")
            info.addWidget(dl)
        rl.addLayout(info, stretch=1)

        del_btn = QPushButton("\u2715")
        del_btn.setFixedSize(24, 24)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet("QPushButton { background: transparent; border: none; color: #DC2626; font-size: 14px; }"
                              "QPushButton:hover { background: #FEE2E2; border-radius: 4px; }")
        del_btn.clicked.connect(lambda: self._delete(item["timeline_id"]))
        rl.addWidget(del_btn)

        return row

    def _add_timeline(self):
        dlg = TimelineFormDialog(self._repo, self._case_id, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.timeline_data()
        data["case_id"] = self._case_id
        self._repo.create_timeline(data)
        self._load()
        self.timeline_changed.emit()

    def _toggle(self, item, checked):
        self._repo.update_timeline(item["timeline_id"], is_completed=checked)
        self._load()
        self.timeline_changed.emit()

    def _delete(self, timeline_id):
        reply = QMessageBox.question(
            self, "Delete Event", "Remove this timeline event?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._repo.delete_timeline(timeline_id)
            self._load()
            self.timeline_changed.emit()


def clear_layout_inner(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            clear_layout_inner(item.layout())


class CaseDetailView(QDialog):
    def __init__(self, repo, case, viewer_user, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._case = case
        self._viewer_user = viewer_user
        self._is_lawyer = viewer_user["role"] == "lawyer"
        self.setWindowTitle(f"Case Details — {case['case_number']}")
        self.resize(660, 720)
        self.setMinimumSize(520, 540)
        self._build()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)

        client = self._repo.get_user(self._case["client_id"])
        client_name = _client_display_name(client)
        lawyer = self._repo.get_user(self._case["lawyer_id"])
        lawyer_name = f"{lawyer['first_name']} {lawyer['last_name']}" if lawyer else "—"

        info_grid = QGridLayout()
        info_grid.setVerticalSpacing(8)
        info_grid.setHorizontalSpacing(16)
        info_grid.setColumnStretch(1, 1)

        fields = [
            ("Case #", self._case["case_number"]),
            ("Title", self._case["title"]),
            ("Type", self._case["case_type"].capitalize()),
            ("Status", None),
            ("Client", client_name),
            ("Lawyer", lawyer_name),
            ("Court", self._case.get("court", "") or "—"),
            ("Opposing Party", self._case.get("opposing_party", "") or "—"),
            ("Filing Date", self._case.get("filing_date", "") or "—"),
            ("Description", self._case["description"] or "No description."),
            ("Created", self._case["created_at"][:10]),
        ]
        for r, (label, value) in enumerate(fields):
            lbl = QLabel(label)
            lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {NAVY}; border: none;")
            info_grid.addWidget(lbl, r, 0, Qt.AlignRight | Qt.AlignTop)
            if label == "Status":
                info_grid.addWidget(_status_badge(self._case["status"]), r, 1)
            else:
                val = QLabel(value)
                val.setWordWrap(True)
                val.setStyleSheet(f"font-size: 13px; color: {TEXT_DARK}; border: none;")
                info_grid.addWidget(val, r, 1)

        layout.addLayout(info_grid)

        if self._is_lawyer:
            edit_btn = QPushButton("Edit Case Details")
            edit_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {STEEL}; border: 1px solid {STEEL};"
                                   f" border-radius: 4px; padding: 6px 18px; font-size: 12px; font-weight: bold; }}"
                                   f"QPushButton:hover {{ background: {STEEL}; color: {WHITE}; }}")
            edit_btn.setFixedWidth(180)
            edit_btn.clicked.connect(lambda: self.done(2))
            eb_row = QHBoxLayout()
            eb_row.addWidget(edit_btn)
            eb_row.addStretch()
            layout.addLayout(eb_row)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(f"color: {BORDER}; border: none; margin: 4px 0;")
        layout.addWidget(separator)

        self._file_list = CaseFileListWidget(
            self._repo, self._case["case_id"],
            self._viewer_user["user_id"], self._viewer_user["role"],
        )
        layout.addWidget(self._file_list)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"color: {BORDER}; border: none; margin: 4px 0;")
        layout.addWidget(sep2)

        self._tasks_widget = CaseTasksWidget(
            self._repo, self._case["case_id"],
            self._viewer_user["user_id"], self._viewer_user["role"],
        )
        layout.addWidget(self._tasks_widget)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        sep3.setStyleSheet(f"color: {BORDER}; border: none; margin: 4px 0;")
        layout.addWidget(sep3)

        self._timeline_widget = CaseTimelineWidget(
            self._repo, self._case["case_id"],
            self._viewer_user["user_id"], self._viewer_user["role"],
        )
        layout.addWidget(self._timeline_widget)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none;"
                                f" border-radius: 4px; padding: 8px 24px; font-size: 13px; font-weight: bold; }}"
                                f"QPushButton:hover {{ background: {STEEL}; }}")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
