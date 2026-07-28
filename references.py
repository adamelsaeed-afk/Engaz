import os
import shutil

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QScrollArea, QFrame, QDialog, QDialogButtonBox,
    QTabWidget, QFileDialog, QSpinBox, QComboBox, QSizePolicy,
    QGraphicsDropShadowEffect, QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QUrl, QTimer
from PySide6.QtGui import QColor, QDesktopServices

from invoicesystem import ArrowComboBox

from engaz_constants import (
    NAVY, STEEL, WHITE, CARD_BG, TEXT_DARK, TEXT_GRAY,
    GREEN, AMBER, RED, BORDER, _format_time, clear_layout,
)

LAW_BOOKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "law_books")

def _field_style():
    return f"padding: 6px 8px; border: 1px solid {BORDER}; border-radius: 4px;" \
           f" font-size: 13px; color: {TEXT_DARK}; background: {WHITE};"


def _ensure_law_books_dir():
    if not os.path.exists(LAW_BOOKS_DIR):
        os.makedirs(LAW_BOOKS_DIR)


class AddBookDialog(QDialog):
    def __init__(self, repo, user, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._user = user
        self._pdf_path = ""
        self._pdf_filename = ""
        self.setWindowTitle("Add Law Book")
        self.resize(480, 400)
        self._build()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)

        lbl = QLabel("Add New Law Book Reference")
        lbl.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        layout.addWidget(lbl)

        fields = [
            ("Title *", QLineEdit()),
            ("Author", QLineEdit()),
            ("Edition", QLineEdit()),
            ("ISBN", QLineEdit()),
        ]
        self._inputs = {}
        for label, widget in fields:
            row = QHBoxLayout()
            rl = QLabel(label)
            rl.setFixedWidth(80)
            rl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {TEXT_DARK}; border: none;")
            row.addWidget(rl)
            widget.setStyleSheet(_field_style())
            row.addWidget(widget, stretch=1)
            layout.addLayout(row)
            self._inputs[label.replace(" *", "").lower()] = widget

        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel("Category"))
        cat_row.itemAt(0).widget().setFixedWidth(80)
        cat_row.itemAt(0).widget().setStyleSheet(f"font-size: 12px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        self._category = ArrowComboBox()
        self._category.addItems(["Corporate", "Penal", "Civil", "Labor", "Other"])
        self._category.setStyleSheet(_field_style())
        cat_row.addWidget(self._category, stretch=1)
        layout.addLayout(cat_row)

        pdf_row = QHBoxLayout()
        pdf_row.addWidget(QLabel("PDF File *"))
        pdf_row.itemAt(0).widget().setFixedWidth(80)
        pdf_row.itemAt(0).widget().setStyleSheet(f"font-size: 12px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        self._pdf_label = QLabel("No file selected")
        self._pdf_label.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 12px; border: 1px solid {BORDER};"
                                      f" padding: 6px 8px; border-radius: 4px; background: {CARD_BG};")
        self._pdf_label.setWordWrap(True)
        pdf_row.addWidget(self._pdf_label, stretch=1)
        pdf_btn = QPushButton("Browse...")
        pdf_btn.setStyleSheet(f"QPushButton {{ background: {STEEL}; color: {WHITE}; border: none;"
                              f" border-radius: 4px; padding: 6px 12px; font-size: 12px; font-weight: bold; }}")
        pdf_btn.clicked.connect(self._browse_pdf)
        pdf_row.addWidget(pdf_btn)
        layout.addLayout(pdf_row)

        layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.setStyleSheet(f"""
            QPushButton {{ padding: 6px 16px; border-radius: 4px; font-size: 13px;
                           color: {TEXT_DARK}; background: {WHITE};
                           border: 1px solid {BORDER}; }}
            QPushButton:hover {{ background: {CARD_BG}; }}
        """)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_pdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select PDF", "", "PDF Files (*.pdf)"
        )
        if path:
            self._pdf_path = path
            self._pdf_filename = os.path.basename(path)
            self._pdf_label.setText(self._pdf_filename)

    def _on_accept(self):
        title = self._inputs["title"].text().strip()
        if not title:
            QMessageBox.warning(self, "Validation", "Title is required.")
            return
        if not self._pdf_path:
            QMessageBox.warning(self, "Validation", "PDF file is required.")
            return
        book_id = self._repo._next_id("law_books", "book")
        ext = os.path.splitext(self._pdf_filename)[1]
        safe_name = f"{book_id}{ext}"
        _ensure_law_books_dir()
        try:
            shutil.copy2(self._pdf_path, os.path.join(LAW_BOOKS_DIR, safe_name))
        except OSError as e:
            QMessageBox.warning(self, "Error", f"Could not copy file: {e}")
            return
        data = {
            "title": title,
            "author": self._inputs["author"].text().strip(),
            "edition": self._inputs["edition"].text().strip(),
            "isbn": self._inputs["isbn"].text().strip(),
            "category": self._category.currentText(),
            "file_name": safe_name,
            "added_by": self._user["user_id"],
        }
        self._repo.create_law_book(data)
        self.accept()


class AddCommentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Comment")
        self.resize(460, 320)
        self._build()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Title"))
        layout.itemAt(layout.count() - 1).widget().setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {TEXT_DARK}; border: none;"
        )
        self._title_input = QLineEdit()
        self._title_input.setStyleSheet(_field_style())
        layout.addWidget(self._title_input)

        pg_row = QHBoxLayout()
        pg_row.addWidget(QLabel("Page #"))
        pg_row.itemAt(pg_row.count() - 1).widget().setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {TEXT_DARK}; border: none;"
        )
        self._page_input = QSpinBox()
        self._page_input.setMinimum(1)
        self._page_input.setMaximum(9999)
        self._page_input.setValue(1)
        self._page_input.setStyleSheet(_field_style())
        pg_row.addWidget(self._page_input)
        pg_row.addStretch()
        layout.addLayout(pg_row)

        layout.addWidget(QLabel("Comment"))
        layout.itemAt(layout.count() - 1).widget().setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {TEXT_DARK}; border: none;"
        )
        self._content_input = QTextEdit()
        self._content_input.setStyleSheet(_field_style())
        self._content_input.setMaximumHeight(100)
        layout.addWidget(self._content_input)

        layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.setStyleSheet(f"""
            QPushButton {{ padding: 6px 16px; border-radius: 4px; font-size: 13px;
                           color: {TEXT_DARK}; background: {WHITE};
                           border: 1px solid {BORDER}; }}
            QPushButton:hover {{ background: {CARD_BG}; }}
        """)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        if not self._title_input.text().strip():
            return
        if not self._content_input.toPlainText().strip():
            return
        self.accept()


    def get_data(self):
        return {
            "title": self._title_input.text().strip(),
            "page_number": self._page_input.value(),
            "content": self._content_input.toPlainText().strip(),
        }


class BookChatWidget(QWidget):
    def __init__(self, repo, user, book_id, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._user = user
        self._book_id = book_id
        self._build()
        self._refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("border: none; background: transparent;")
        self._msg_container = QWidget()
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(8, 8, 8, 8)
        self._msg_layout.setSpacing(4)
        self._msg_layout.addStretch()
        self._scroll.setWidget(self._msg_container)
        layout.addWidget(self._scroll, stretch=1)

        input_area = QFrame()
        input_area.setStyleSheet(f"background: {WHITE}; border-top: 1px solid {BORDER};")
        input_row = QHBoxLayout(input_area)
        input_row.setContentsMargins(8, 6, 8, 6)
        input_row.setSpacing(6)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a message...")
        self._input.setStyleSheet(_field_style())
        self._input.returnPressed.connect(self._send)
        input_row.addWidget(self._input, stretch=1)
        send_btn = QPushButton("Send")
        send_btn.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none;"
                               f" border-radius: 4px; padding: 6px 14px; font-size: 12px; font-weight: bold; }}")
        send_btn.clicked.connect(self._send)
        input_row.addWidget(send_btn)
        layout.addWidget(input_area)

    def _clear_messages(self):
        clear_layout(self._msg_layout)

    def _refresh(self):
        self._clear_messages()
        chats = self._repo.get_book_chats(self._book_id)
        for chat in chats:
            user = self._repo.get_user(chat["user_id"])
            name = f"{user['first_name']} {user['last_name']}" if user else "Unknown"
            is_self = chat["user_id"] == self._user["user_id"]
            bubble = QFrame()
            bubble.setStyleSheet(f"background: {'#EBF0F5' if is_self else WHITE};"
                                 f" border: 1px solid {BORDER}; border-radius: 8px;")
            bl = QVBoxLayout(bubble)
            bl.setContentsMargins(10, 6, 10, 6)
            bl.setSpacing(2)
            hdr = QHBoxLayout()
            nl = QLabel(name)
            nl.setStyleSheet(f"font-weight: bold; font-size: 11px; color: {NAVY if is_self else TEXT_GRAY}; border: none;")
            hdr.addWidget(nl)
            hdr.addStretch()
            tl = QLabel(_format_time(chat["created_at"]))
            tl.setStyleSheet(f"font-size: 10px; color: {TEXT_GRAY}; border: none;")
            hdr.addWidget(tl)
            bl.addLayout(hdr)
            cl = QLabel(chat["content"])
            cl.setWordWrap(True)
            cl.setStyleSheet(f"font-size: 12px; color: {TEXT_DARK}; border: none;")
            bl.addWidget(cl)
            self._msg_layout.addWidget(bubble)
        self._msg_layout.addStretch()
        QTimer.singleShot(30, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        if not self.isVisible():
            return
        self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum())

    def _send(self):
        content = self._input.text().strip()
        if not content:
            return
        self._input.clear()
        self._repo.create_book_chat({
            "book_id": self._book_id,
            "user_id": self._user["user_id"],
            "content": content,
        })
        self._refresh()


class BookCommentsWidget(QWidget):
    def __init__(self, repo, user, book_id, file_name, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._user = user
        self._book_id = book_id
        self._file_name = file_name
        self._build()
        self._refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.addStretch()
        add_btn = QPushButton("+ Add Comment")
        add_btn.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none;"
                              f" border-radius: 4px; padding: 6px 14px; font-size: 12px; font-weight: bold; }}")
        add_btn.clicked.connect(self._add_comment)
        header.addWidget(add_btn)
        layout.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("border: none; background: transparent;")
        self._container = QWidget()
        self._list_layout = QVBoxLayout(self._container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()
        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll, stretch=1)

    def _clear(self):
        clear_layout(self._list_layout)

    def _refresh(self):
        self._clear()
        comments = self._repo.get_book_comments(self._book_id)
        for c in comments:
            user = self._repo.get_user(c["user_id"])
            name = f"{user['first_name']} {user['last_name']}" if user else "Unknown"
            card = QFrame()
            card.setCursor(Qt.PointingHandCursor)
            page_num = c.get("page_number", 1)
            card.setToolTip(f"Click to open PDF at page {page_num}")
            card.setStyleSheet(f"""
                QFrame {{ background: {WHITE}; border: 1px solid {BORDER}; border-radius: 6px; }}
                QFrame:hover {{ border-color: {STEEL}; background: {CARD_BG}; }}
            """)
            card.mousePressEvent = lambda e, pn=page_num: self._open_at_page(pn)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 8, 12, 8)
            cl.setSpacing(4)
            top = QHBoxLayout()
            ct = QLabel(c["title"])
            ct.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {TEXT_DARK}; border: none;")
            top.addWidget(ct)
            top.addStretch()
            pg_badge = QLabel(f"p.{c.get('page_number', 0)}")
            pg_badge.setStyleSheet(f"background: {STEEL}; color: {WHITE}; padding: 2px 8px;"
                                   f" border-radius: 8px; font-size: 10px; font-weight: bold;")
            top.addWidget(pg_badge)
            cl.addLayout(top)
            body = QLabel(c["content"])
            body.setWordWrap(True)
            body.setStyleSheet(f"font-size: 12px; color: {TEXT_DARK}; border: none;")
            cl.addWidget(body)
            meta = QLabel(f"{name} · {_format_time(c['created_at'])}")
            meta.setStyleSheet(f"font-size: 10px; color: {TEXT_GRAY}; border: none;")
            cl.addWidget(meta)
            self._list_layout.addWidget(card)
        self._list_layout.addStretch()

    def _add_comment(self):
        dlg = AddCommentDialog(parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.get_data()
        self._repo.create_book_comment({
            "book_id": self._book_id,
            "user_id": self._user["user_id"],
            **data,
        })
        self._refresh()

    def _open_at_page(self, page_num):
        path = os.path.join(LAW_BOOKS_DIR, self._file_name)
        if not os.path.exists(path):
            QMessageBox.warning(self, "File Not Found",
                                f"The PDF could not be found at:\n{path}")
            return
        url = QUrl.fromLocalFile(path)
        url.setFragment(f"page={page_num}")
        if not QDesktopServices.openUrl(url):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))


class BookDetailView(QDialog):
    def __init__(self, repo, user, book, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._user = user
        self._book = book
        self.setWindowTitle(book["title"])
        self.resize(680, 560)
        self.setMinimumSize(500, 400)
        self._build()

    def _build(self):
        self.setStyleSheet(f"background: {WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.setSpacing(8)

        meta_frame = QFrame()
        meta_frame.setStyleSheet(f"background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 8px;")
        ml = QVBoxLayout(meta_frame)
        ml.setContentsMargins(16, 12, 16, 12)
        ml.setSpacing(4)
        title_lbl = QLabel(self._book["title"])
        title_lbl.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        ml.addWidget(title_lbl)
        details = []
        if self._book.get("author"):
            details.append(f"Author: {self._book['author']}")
        if self._book.get("edition"):
            details.append(f"Edition: {self._book['edition']}")
        if self._book.get("isbn"):
            details.append(f"ISBN: {self._book['isbn']}")
        if self._book.get("category"):
            details.append(f"Category: {self._book['category']}")
        detail_lbl = QLabel(" · ".join(details))
        detail_lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_GRAY}; border: none;")
        ml.addWidget(detail_lbl)
        layout.addWidget(meta_frame)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open PDF")
        open_btn.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none;"
                               f" border-radius: 4px; padding: 6px 20px; font-size: 13px; font-weight: bold; }}")
        open_btn.clicked.connect(self._open_pdf)
        btn_row.addWidget(open_btn)

        fav_btn = QPushButton("\u2605 Bookmark" if self._book.get("is_favorite") else "\u2606 Bookmark")
        fav_btn.setCursor(Qt.PointingHandCursor)
        fav_btn.clicked.connect(self._toggle_favorite)
        fav_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {AMBER}; border: 1px solid {BORDER};"
            f" border-radius: 4px; padding: 6px 14px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: #FFF3E0; }}"
        )
        self._fav_btn = fav_btn
        btn_row.addWidget(fav_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 4px; background: {WHITE}; }}
            QTabBar::tab {{ padding: 6px 16px; font-size: 12px; color: {TEXT_DARK}; background: {CARD_BG};
                            border: 1px solid {BORDER}; border-bottom: none;
                            border-top-left-radius: 4px; border-top-right-radius: 4px; }}
            QTabBar::tab:selected {{ background: {WHITE}; font-weight: bold; }}
        """)
        self._chat_widget = BookChatWidget(self._repo, self._user, self._book["book_id"])
        self._comments_widget = BookCommentsWidget(self._repo, self._user, self._book["book_id"], self._book["file_name"])
        tabs.addTab(self._chat_widget, "Chat")
        tabs.addTab(self._comments_widget, "Comments")
        layout.addWidget(tabs, stretch=1)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {STEEL}; border: 1px solid {STEEL};"
                                f" border-radius: 4px; padding: 6px 20px; font-size: 12px; }}")
        close_btn.clicked.connect(self.accept)
        cr = QHBoxLayout()
        cr.addStretch()
        cr.addWidget(close_btn)
        layout.addLayout(cr)

    def _open_pdf(self):
        path = os.path.join(LAW_BOOKS_DIR, self._book["file_name"])
        if os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            QMessageBox.warning(self, "File Not Found",
                                f"The PDF could not be found at:\n{path}")

    def _toggle_favorite(self):
        self._repo.toggle_law_book_favorite(self._book["book_id"])
        self._book = self._repo.get_law_book(self._book["book_id"]) or self._book
        if hasattr(self, "_fav_btn"):
            self._fav_btn.setText("\u2605 Bookmark" if self._book.get("is_favorite") else "\u2606 Bookmark")


class BookListView(QWidget):
    book_selected = Signal(dict)

    CATEGORIES = ["All", "Corporate", "Penal", "Civil", "Labor", "Other"]

    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._fav_only = False
        self._build()
        self.refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search by title, author, or category...")
        self._search.setStyleSheet(_field_style())
        self._search.textChanged.connect(self._on_search)
        filter_row.addWidget(self._search, stretch=1)

        self._category_filter = QComboBox()
        self._category_filter.addItems(self.CATEGORIES)
        self._category_filter.setStyleSheet(_field_style())
        self._category_filter.currentTextChanged.connect(self._on_search)
        filter_row.addWidget(self._category_filter)

        self._fav_btn = QPushButton("\u2606")
        self._fav_btn.setFixedSize(32, 32)
        self._fav_btn.setToolTip("Show favorites only")
        self._fav_btn.setCursor(Qt.PointingHandCursor)
        self._fav_btn.clicked.connect(self._toggle_fav_filter)
        self._fav_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {AMBER}; border: 1px solid {BORDER};"
            f" border-radius: 4px; font-size: 16px; }}"
            f"QPushButton:hover {{ background: #FFF3E0; }}"
        )
        filter_row.addWidget(self._fav_btn)

        layout.addLayout(filter_row)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("border: none; background: transparent;")
        self._container = QWidget()
        self._list_layout = QVBoxLayout(self._container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch()
        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll, stretch=1)

    def _toggle_fav_filter(self):
        self._fav_only = not self._fav_only
        self._fav_btn.setText("\u2605" if self._fav_only else "\u2606")
        self._fav_btn.setStyleSheet(
            f"QPushButton {{ background: {'#FFF3E0' if self._fav_only else 'transparent'}; "
            f"color: {AMBER}; border: 1px solid {BORDER};"
            f" border-radius: 4px; font-size: 16px; }}"
            f"QPushButton:hover {{ background: #FFF3E0; }}"
        )
        self.refresh()

    def _clear(self):
        clear_layout(self._list_layout)

    def refresh(self):
        self._clear()
        self._all_books = self._repo.get_all_law_books()
        query = self._search.text().strip().lower()
        cat = self._category_filter.currentText()
        books = self._all_books
        if query:
            books = [b for b in books
                     if query in b.get("title", "").lower()
                     or query in b.get("author", "").lower()
                     or query in b.get("category", "").lower()]
        if cat and cat != "All":
            books = [b for b in books if b.get("category", "") == cat]
        if self._fav_only:
            books = [b for b in books if b.get("is_favorite", False)]
        if not books:
            empty = QLabel("No law books found")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 13px; padding: 30px; border: none;")
            self._list_layout.addWidget(empty)
        else:
            for book in books:
                card = self._make_book_card(book)
                self._list_layout.addWidget(card)
        self._list_layout.addStretch()

    def _on_search(self):
        self.refresh()

    def _make_book_card(self, book):
        card = QFrame()
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet(f"""
            QFrame {{ background: {WHITE}; border: 1px solid {BORDER}; border-radius: 8px; }}
            QFrame:hover {{ border-color: {STEEL}; background: {CARD_BG}; }}
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 20))
        card.setGraphicsEffect(shadow)
        outer = QHBoxLayout(card)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(8)

        cl = QVBoxLayout()
        cl.setSpacing(4)
        title_lbl = QLabel(book.get("title", ""))
        title_lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        cl.addWidget(title_lbl)

        info = []
        if book.get("author"):
            info.append(book["author"])
        if book.get("edition"):
            info.append(book["edition"])
        if book.get("category"):
            info.append(book["category"])
        il = QLabel(" · ".join(info))
        il.setStyleSheet(f"font-size: 11px; color: {TEXT_GRAY}; border: none;")
        cl.addWidget(il)
        outer.addLayout(cl, stretch=1)

        fav_btn = QPushButton("\u2605" if book.get("is_favorite") else "\u2606")
        fav_btn.setFixedSize(28, 28)
        fav_btn.setCursor(Qt.PointingHandCursor)
        fav_color = AMBER if book.get("is_favorite") else "#D1D5DB"
        fav_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {fav_color}; border: none; font-size: 18px; }}"
            f"QPushButton:hover {{ color: {AMBER}; }}"
        )
        fav_btn.clicked.connect(lambda chk=False, b=book: self._toggle_fav(b))
        outer.addWidget(fav_btn)

        card.mousePressEvent = lambda e, b=book: self.book_selected.emit(dict(b))
        return card

    def _toggle_fav(self, book):
        self._repo.toggle_law_book_favorite(book["book_id"])
        self.refresh()


class LawLibraryPage(QWidget):
    def __init__(self, repo, user, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._user = user
        self.setStyleSheet(f"background: {WHITE};")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        heading = QLabel("References")
        heading.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {TEXT_DARK}; border: none;")
        header.addWidget(heading)
        header.addStretch()
        add_btn = QPushButton("+ Add Book")
        add_btn.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: {WHITE}; border: none;"
                              f" border-radius: 4px; padding: 8px 18px; font-size: 13px; font-weight: bold; }}")
        add_btn.clicked.connect(self._open_add_dialog)
        header.addWidget(add_btn)
        layout.addLayout(header)

        self._book_list = BookListView(self._repo)
        self._book_list.book_selected.connect(self._open_detail)
        layout.addWidget(self._book_list, stretch=1)

    def refresh(self):
        self._book_list.refresh()

    def _open_detail(self, book):
        dlg = BookDetailView(self._repo, self._user, book, parent=self)
        dlg.exec()

    def _open_add_dialog(self):
        dlg = AddBookDialog(self._repo, self._user, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh()
