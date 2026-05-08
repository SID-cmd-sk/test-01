# ui/global_search_widget.py
"""
Global Search Bar + Results Popup.

A floating search bar that can be dropped into any dashboard header.
Searches across SRs, Users, and Tasks in real-time (debounced).

Usage:
    from ui.global_search_widget import GlobalSearchBar
    bar = GlobalSearchBar(parent=self)
    bar.result_selected.connect(self._on_search_result)
    header_layout.addWidget(bar)
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QLabel,
    QListWidget, QListWidgetItem, QFrame, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, pyqtSlot
from PyQt6.QtGui import QKeySequence, QShortcut


class SearchWorker(QThread):
    results_ready = pyqtSignal(list)

    def __init__(self, query: str):
        super().__init__()
        self.query = query

    def run(self):
        try:
            from services.search_service import search
            results = search(self.query, types=["all"], max_results=30)
            self.results_ready.emit([r.to_dict() for r in results])
        except Exception:
            self.results_ready.emit([])


class SearchResultsPopup(QFrame):
    item_selected = pyqtSignal(dict)   # emits the result dict

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("search_popup")
        self.setStyleSheet("""
            QFrame#search_popup {
                background: white;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
            }
        """)
        self.setFixedWidth(520)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("font-size: 11px; color: #94A3B8; padding: 0 4px;")
        lay.addWidget(self._count_lbl)

        self._list = QListWidget()
        self._list.setFrameShape(QFrame.Shape.NoFrame)
        self._list.setStyleSheet("""
            QListWidget { border: none; outline: none; }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 6px;
                border-bottom: 1px solid #F1F5F9;
            }
            QListWidget::item:hover { background: #F1F5F9; }
            QListWidget::item:selected { background: #EFF6FF; color: #1E293B; }
        """)
        self._list.itemDoubleClicked.connect(self._on_select)
        self._list.itemActivated.connect(self._on_select)
        lay.addWidget(self._list)

        self._empty_lbl = QLabel("No results found.")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet("color: #94A3B8; padding: 20px; font-size: 13px;")
        self._empty_lbl.setVisible(False)
        lay.addWidget(self._empty_lbl)

    def show_results(self, results: list):
        self._list.clear()
        if not results:
            self._list.setVisible(False)
            self._empty_lbl.setVisible(True)
            self._count_lbl.setText("No results")
            self.setFixedHeight(80)
            return

        self._list.setVisible(True)
        self._empty_lbl.setVisible(False)
        self._count_lbl.setText(f"{len(results)} result{'s' if len(results) != 1 else ''}")

        type_icons = {"sr": "🔧", "user": "👤", "task": "✅"}
        type_labels = {"sr": "SR", "user": "User", "task": "Task"}

        for r in results:
            doc      = r.get("doc", {})
            rtype    = r.get("type", "")
            snippet  = r.get("snippet", "")
            icon     = type_icons.get(rtype, "📄")
            type_lbl = type_labels.get(rtype, rtype.upper())

            # Build display text
            if rtype == "sr":
                sr_num = doc.get("sr_number", "")
                title  = doc.get("title", "Untitled")
                status = doc.get("status", "")
                main   = f"{icon} [{type_lbl}]  {sr_num}  {title}"
                sub    = f"Status: {status}  •  {snippet}"
            elif rtype == "user":
                name  = doc.get("name", "Unknown")
                email = doc.get("email", "")
                role  = doc.get("role", "")
                main  = f"{icon} [{type_lbl}]  {name}"
                sub   = f"{email}  •  {role}"
            else:
                title = doc.get("title", doc.get("task_title", "Task"))
                main  = f"{icon} [{type_lbl}]  {title}"
                sub   = snippet

            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, r)

            # Custom widget for each row
            row_widget = QWidget()
            row_lay = QVBoxLayout(row_widget)
            row_lay.setContentsMargins(4, 2, 4, 2)
            row_lay.setSpacing(1)

            lbl_main = QLabel(main)
            lbl_main.setStyleSheet("font-size: 13px; font-weight: 500; color: #1E293B;")
            lbl_sub  = QLabel(sub)
            lbl_sub.setStyleSheet("font-size: 11px; color: #64748B;")
            lbl_sub.setMaximumWidth(480)

            row_lay.addWidget(lbl_main)
            row_lay.addWidget(lbl_sub)
            row_widget.setFixedHeight(48)

            item.setSizeHint(row_widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row_widget)

        height = min(len(results) * 52 + 50, 400)
        self.setFixedHeight(height)

    def _on_select(self, item: QListWidgetItem):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.item_selected.emit(data)
            self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        super().keyPressEvent(event)


class GlobalSearchBar(QWidget):
    """
    Search bar with debounced live search and floating results popup.
    Drop into any dashboard header layout.
    """
    result_selected = pyqtSignal(dict)   # emits SearchResult dict on selection

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker:   SearchWorker | None = None
        self._popup:    SearchResultsPopup | None = None
        self._debounce  = QTimer()
        self._debounce.setInterval(250)    # 250ms debounce
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._do_search)
        self._build_ui()

        # Global shortcut: Ctrl+K to focus search
        shortcut = QShortcut(QKeySequence("Ctrl+K"), parent or self)
        shortcut.activated.connect(self._input.setFocus)

    def _build_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self._input = QLineEdit()
        self._input.setPlaceholderText("🔍  Search SRs, users, tasks…  (Ctrl+K)")
        self._input.setFixedHeight(36)
        self._input.setMinimumWidth(280)
        self._input.setStyleSheet("""
            QLineEdit {
                background: #F1F5F9;
                border: 1px solid #E2E8F0;
                border-radius: 18px;
                padding: 0 16px;
                font-size: 13px;
                color: #1E293B;
            }
            QLineEdit:focus {
                background: white;
                border-color: #3B82F6;
            }
        """)
        self._input.textChanged.connect(self._on_text_changed)
        self._input.returnPressed.connect(self._do_search)
        lay.addWidget(self._input)

    def _on_text_changed(self, text: str):
        if len(text.strip()) < 2:
            if self._popup:
                self._popup.hide()
            return
        self._debounce.start()

    def _do_search(self):
        query = self._input.text().strip()
        if len(query) < 2:
            return
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
        self._worker = SearchWorker(query)
        self._worker.results_ready.connect(self._show_results)
        self._worker.start()

    @pyqtSlot(list)
    def _show_results(self, results: list):
        if self._popup is None:
            # Parent to the main window so it floats above the whole app
            main_win = QApplication.activeWindow()
            self._popup = SearchResultsPopup(main_win)
            self._popup.item_selected.connect(self.result_selected)

        # Position popup below the search bar
        pos = self._input.mapToGlobal(self._input.rect().bottomLeft())
        pos.setY(pos.y() + 4)
        self._popup.move(pos)
        self._popup.show_results(results)
        self._popup.show()
        self._input.setFocus()

    def clear(self):
        self._input.clear()
        if self._popup:
            self._popup.hide()
