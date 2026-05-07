# ui/pipeline_builder.py
"""
Pipeline Template Builder — Admin only.
Create / edit / delete multi-step SR approval templates.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QDialog, QFormLayout,
    QLineEdit, QTextEdit, QComboBox, QCheckBox, QMessageBox,
    QFrame, QScrollArea, QSizePolicy, QSplitter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont

from services.pipeline_service import pipeline_service
from utils.helpers import format_datetime, utc_now_iso


# ── Workers ───────────────────────────────────────────────────────────────────

class LoadTemplatesWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)
    def run(self):
        try:
            self.done.emit(pipeline_service.get_templates())
        except Exception as e:
            self.error.emit(str(e))


class SaveTemplateWorker(QThread):
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)
    def __init__(self, template): super().__init__(); self.template = template
    def run(self):
        try:
            self.done.emit(pipeline_service.save_template(self.template))
        except Exception as e:
            self.error.emit(str(e))


class DeleteTemplateWorker(QThread):
    done  = pyqtSignal()
    error = pyqtSignal(str)
    def __init__(self, tid): super().__init__(); self.tid = tid
    def run(self):
        try:
            pipeline_service.delete_template(self.tid)
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))


# ── Step Editor ───────────────────────────────────────────────────────────────

class StepEditorRow(QFrame):
    """Single step row inside the template editor."""
    delete_requested = pyqtSignal(object)   # emits self

    def __init__(self, index: int, step: dict = None, parent=None):
        super().__init__(parent)
        self.index = index
        self.setObjectName("pipeline_step")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        step = step or {}
        self._build_ui(step)

    def _build_ui(self, step: dict):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # Index badge
        idx_lbl = QLabel(str(self.index + 1))
        idx_lbl.setFixedSize(28, 28)
        idx_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        idx_lbl.setStyleSheet("""
            background: #3B82F6; color: white; border-radius: 14px;
            font-weight: bold; font-size: 13px;
        """)
        lay.addWidget(idx_lbl)

        form = QVBoxLayout()
        row1 = QHBoxLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Step name (e.g. Welcome Letter)")
        self.name_input.setText(step.get("name", ""))
        self.name_input.setFixedHeight(32)
        row1.addWidget(self.name_input, 3)

        self.role_combo = QComboBox()
        self.role_combo.addItems(["technical", "manager", "admin"])
        self.role_combo.setCurrentText(step.get("approver_role", "technical"))
        self.role_combo.setFixedHeight(32)
        row1.addWidget(QLabel("Approver:"))
        row1.addWidget(self.role_combo, 1)

        self.required_chk  = QCheckBox("Required")
        self.required_chk.setChecked(step.get("required", True))
        self.skippable_chk = QCheckBox("Skippable")
        self.skippable_chk.setChecked(step.get("skippable", True))
        row1.addWidget(self.required_chk)
        row1.addWidget(self.skippable_chk)

        form.addLayout(row1)

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Step description (optional)")
        self.desc_input.setText(step.get("description", ""))
        self.desc_input.setFixedHeight(30)
        form.addWidget(self.desc_input)

        lay.addLayout(form, 1)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(30, 30)
        del_btn.setStyleSheet("""
            QPushButton { background: #EF4444; color: white; border: none;
                          border-radius: 15px; font-weight: bold; font-size: 14px; }
            QPushButton:hover { background: #DC2626; }
        """)
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        lay.addWidget(del_btn)

    def to_dict(self) -> dict:
        return {
            "index":        self.index,
            "name":         self.name_input.text().strip(),
            "description":  self.desc_input.text().strip(),
            "approver_role": self.role_combo.currentText(),
            "required":     self.required_chk.isChecked(),
            "skippable":    self.skippable_chk.isChecked(),
        }


# ── Template Editor Dialog ────────────────────────────────────────────────────

class TemplateEditorDialog(QDialog):
    saved = pyqtSignal(dict)

    def __init__(self, template: dict = None, parent=None):
        super().__init__(parent)
        self.template  = template or {}
        self._steps:   list[StepEditorRow] = []
        self._worker   = None
        self.setWindowTitle("Pipeline Template Editor")
        self.setMinimumSize(700, 600)
        self._build_ui()
        if template:
            self._load_template(template)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 20, 20, 20)

        ttl = QLabel("🔧  Pipeline Template Editor")
        ttl.setStyleSheet("font-size: 16px; font-weight: bold; color: #0F172A;")
        lay.addWidget(ttl)

        # Template meta
        meta_form = QFormLayout()
        meta_form.setSpacing(8)
        self.tpl_name  = QLineEdit(); self.tpl_name.setPlaceholderText("Template name");  self.tpl_name.setFixedHeight(36)
        self.tpl_desc  = QLineEdit(); self.tpl_desc.setPlaceholderText("Short description"); self.tpl_desc.setFixedHeight(36)
        meta_form.addRow("Template Name *:", self.tpl_name)
        meta_form.addRow("Description:",     self.tpl_desc)
        lay.addLayout(meta_form)

        # Steps header
        sh = QHBoxLayout()
        sh.addWidget(QLabel("Pipeline Steps"))
        sh.addStretch()
        add_btn = QPushButton("+ Add Step"); add_btn.setObjectName("btn_primary")
        add_btn.setFixedHeight(32); add_btn.clicked.connect(self._add_step)
        sh.addWidget(add_btn)
        lay.addLayout(sh)

        # Scrollable steps area
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.steps_container = QWidget()
        self.steps_layout    = QVBoxLayout(self.steps_container)
        self.steps_layout.setSpacing(6)
        self.steps_layout.setContentsMargins(0, 0, 0, 0)
        self.steps_layout.addStretch()
        scroll.setWidget(self.steps_container)
        lay.addWidget(scroll, 1)

        # Buttons
        self.err_lbl = QLabel(""); self.err_lbl.setObjectName("error_label"); self.err_lbl.setVisible(False)
        lay.addWidget(self.err_lbl)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancel"); cancel.setObjectName("btn_secondary"); cancel.clicked.connect(self.reject)
        self.save_btn = QPushButton("💾  Save Template"); self.save_btn.setObjectName("btn_primary")
        self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel); btn_row.addStretch(); btn_row.addWidget(self.save_btn)
        lay.addLayout(btn_row)

    def _load_template(self, template: dict):
        self.tpl_name.setText(template.get("name", ""))
        self.tpl_desc.setText(template.get("description", ""))
        for step in template.get("steps", []):
            self._add_step(step)

    def _add_step(self, step: dict = None):
        if isinstance(step, bool):
            step = None   # Qt sends False for unchecked signal
        row = StepEditorRow(len(self._steps), step or {}, self.steps_container)
        row.delete_requested.connect(self._remove_step)
        # Insert before the stretch
        self.steps_layout.insertWidget(self.steps_layout.count() - 1, row)
        self._steps.append(row)
        self._reindex()

    def _remove_step(self, row: StepEditorRow):
        self._steps.remove(row)
        self.steps_layout.removeWidget(row)
        row.deleteLater()
        self._reindex()

    def _reindex(self):
        for i, row in enumerate(self._steps):
            row.index = i

    def _save(self):
        name = self.tpl_name.text().strip()
        if not name:
            self.err_lbl.setText("⚠ Template name is required."); self.err_lbl.setVisible(True); return
        if not self._steps:
            self.err_lbl.setText("⚠ Add at least one step."); self.err_lbl.setVisible(True); return
        for row in self._steps:
            if not row.to_dict()["name"]:
                self.err_lbl.setText("⚠ All steps must have a name."); self.err_lbl.setVisible(True); return

        template = dict(self.template)
        template["name"]        = name
        template["description"] = self.tpl_desc.text().strip()
        template["steps"]       = [r.to_dict() for r in self._steps]

        self.save_btn.setEnabled(False); self.save_btn.setText("Saving…")
        self._worker = SaveTemplateWorker(template)
        self._worker.done.connect(self._on_saved)
        self._worker.error.connect(lambda e: (
            self.err_lbl.setText(f"⚠ {e}"), self.err_lbl.setVisible(True),
            self.save_btn.setEnabled(True), self.save_btn.setText("💾  Save Template")
        ))
        self._worker.start()

    def _on_saved(self, result: dict):
        self.saved.emit(result)
        self.accept()


# ── Pipeline Builder Panel ────────────────────────────────────────────────────

class PipelineBuilderPanel(QWidget):
    """Main panel shown inside Admin → Pipeline tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._templates: list[dict] = []
        self._worker = None
        self._build_ui()
        self._load()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        ttl = QLabel("Pipeline Templates"); ttl.setObjectName("section_title"); hdr.addWidget(ttl); hdr.addStretch()
        new_btn = QPushButton("+ New Template"); new_btn.setObjectName("btn_primary")
        new_btn.clicked.connect(self._new_template); hdr.addWidget(new_btn)
        lay.addLayout(hdr)

        info = QLabel("Define multi-step approval processes. Assign templates when creating SRs.")
        info.setObjectName("info_label"); lay.addWidget(info)

        # Splitter: list on left, detail on right
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Template list
        left = QWidget()
        left_lay = QVBoxLayout(left); left_lay.setContentsMargins(0, 0, 0, 0)
        self.tpl_list = QListWidget()
        self.tpl_list.setMinimumWidth(220)
        self.tpl_list.currentRowChanged.connect(self._on_select)
        left_lay.addWidget(self.tpl_list)
        splitter.addWidget(left)

        # Detail panel
        right = QWidget()
        right.setStyleSheet("background: white; border-radius: 8px; border: 1px solid #E2E8F0;")
        self.detail_lay = QVBoxLayout(right)
        self.detail_lay.setContentsMargins(16, 16, 16, 16)
        self.detail_placeholder = QLabel("← Select a template to view details")
        self.detail_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_placeholder.setObjectName("info_label")
        self.detail_lay.addWidget(self.detail_placeholder)
        self._detail_widgets: list[QWidget] = [self.detail_placeholder]
        splitter.addWidget(right)

        splitter.setSizes([240, 500])
        lay.addWidget(splitter, 1)

    def _load(self):
        self._worker = LoadTemplatesWorker()
        self._worker.done.connect(self._on_loaded)
        self._worker.error.connect(lambda e: None)
        self._worker.start()

    @pyqtSlot(list)
    def _on_loaded(self, templates: list):
        self._templates = templates
        self.tpl_list.clear()
        for t in templates:
            item = QListWidgetItem(f"  {t.get('name', 'Unnamed')}")
            item.setData(Qt.ItemDataRole.UserRole, t)
            self.tpl_list.addItem(item)

    def _on_select(self, row: int):
        if row < 0 or row >= len(self._templates):
            return
        self._show_detail(self._templates[row])

    def _show_detail(self, t: dict):
        # Clear
        for w in self._detail_widgets:
            self.detail_lay.removeWidget(w)
            w.deleteLater()
        self._detail_widgets.clear()

        def add(w):
            self.detail_lay.addWidget(w)
            self._detail_widgets.append(w)

        name_lbl = QLabel(t.get("name", "—"))
        name_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #0F172A;")
        add(name_lbl)

        if t.get("description"):
            desc = QLabel(t["description"]); desc.setObjectName("info_label"); desc.setWordWrap(True)
            add(desc)

        steps_lbl = QLabel(f"Steps: {len(t.get('steps', []))}")
        steps_lbl.setStyleSheet("font-size: 12px; color: #64748B; margin-top: 4px;")
        add(steps_lbl)

        for i, s in enumerate(t.get("steps", [])):
            sf = QFrame(); sf.setObjectName("pipeline_step")
            sf_lay = QHBoxLayout(sf); sf_lay.setContentsMargins(10, 8, 10, 8)
            idx = QLabel(str(i+1)); idx.setFixedSize(24, 24)
            idx.setAlignment(Qt.AlignmentFlag.AlignCenter)
            idx.setStyleSheet("background:#3B82F6;color:white;border-radius:12px;font-weight:bold;font-size:11px;")
            sf_lay.addWidget(idx)
            info_lay = QVBoxLayout()
            sname = QLabel(s.get("name","—")); sname.setStyleSheet("font-weight:bold;font-size:12px;")
            sdesc = QLabel(f"Approver: {s.get('approver_role','—')}  |  "
                           f"{'Required' if s.get('required') else 'Optional'}  |  "
                           f"{'Skippable' if s.get('skippable') else 'Not skippable'}")
            sdesc.setObjectName("info_label")
            info_lay.addWidget(sname); info_lay.addWidget(sdesc)
            sf_lay.addLayout(info_lay, 1)
            add(sf)

        spacer = QLabel(""); add(spacer)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_container = QWidget(); btn_container.setLayout(btn_row)

        edit_btn = QPushButton("✏ Edit"); edit_btn.setObjectName("btn_primary")
        edit_btn.clicked.connect(lambda _, tmpl=t: self._edit_template(tmpl))

        del_btn = QPushButton("🗑 Delete"); del_btn.setObjectName("btn_danger")
        del_btn.clicked.connect(lambda _, tmpl=t: self._delete_template(tmpl))

        btn_row.addWidget(edit_btn); btn_row.addWidget(del_btn); btn_row.addStretch()
        add(btn_container)

        self.detail_lay.addStretch()

    def _new_template(self):
        dlg = TemplateEditorDialog(parent=self)
        dlg.saved.connect(lambda _: self._load())
        dlg.exec()

    def _edit_template(self, template: dict):
        dlg = TemplateEditorDialog(template=template, parent=self)
        dlg.saved.connect(lambda _: self._load())
        dlg.exec()

    def _delete_template(self, template: dict):
        if QMessageBox.question(self, "Delete",
            f"Delete template '{template.get('name')}'?\n\nExisting SRs will keep their pipeline state.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        w = DeleteTemplateWorker(template.get("id", ""))
        w.done.connect(self._load)
        w.error.connect(lambda e: QMessageBox.critical(self, "Error", e))
        w.start()
