import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialog, QFileDialog, QFrame, QScrollArea, QGridLayout, QSizePolicy,
    QMenu, QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices

from engaz_constants import (
    NAVY, STEEL, WHITE, CARD_BG, TEXT_DARK, TEXT_GRAY,
    GREEN, AMBER, RED, BORDER, _status_badge,
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

        lbl = QLabel("Select a file to add (path reference only, file is not copied):")
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
            QHeaderView::section {{ background: {STEEL}; color: {WHITE}; padding: 6px;
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
        self._repo.add_case_file({
            "case_id": self._case_id,
            "added_by": self._viewer_user_id,
            "file_name": dlg.file_name(),
            "file_path": dlg.file_path(),
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
        if os.path.exists(file_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        else:
            QMessageBox.warning(self, "File Not Found",
                                f"The file could not be found at:\n{file_path}")


class CaseDetailView(QDialog):
    def __init__(self, repo, case, viewer_user, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._case = case
        self._viewer_user = viewer_user
        self._is_lawyer = viewer_user["role"] == "lawyer"
        self.setWindowTitle(f"Case Details — {case['case_number']}")
        self.resize(620, 540)
        self.setMinimumSize(500, 400)
        self._build()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)

        client = self._repo.get_user(self._case["client_id"])
        client_name = f"{client['first_name']} {client['last_name']}" if client else "—"
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
        layout.addWidget(self._file_list, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none;"
                                f" border-radius: 4px; padding: 8px 24px; font-size: 13px; font-weight: bold; }}"
                                f"QPushButton:hover {{ background: {STEEL}; }}")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
