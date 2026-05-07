# ui/role_builder.py
"""
Role & Permission Builder — Admin only.
Create custom roles, edit permissions of existing roles.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QDialog, QFormLayout,
    QLineEdit, QCheckBox, QMessageBox, QFrame, QScrollArea,
    QGroupBox, QSplitter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont

from utils.auth import DEFAULT_PERMISSIONS
from utils.helpers import utc_now_iso


# ── All available permissions ─────────────────────────────────────────────────

ALL_PERMISSIONS = {
    "SR Management": [
        ("view_own_srs",          "View own SRs"),
        ("view_all_srs",          "View all SRs"),
        ("create_sr",             "Create SRs"),
        ("update_sr_status",      "Update SR status"),
        ("assign_sr",             "Assign SRs to users"),
        ("close_sr",              "Close SRs"),
        ("skip_pipeline_steps",   "Skip pipeline steps (with reason)"),
    ],
    "User Management": [
        ("create_user",           "Create users"),
        ("edit_user",             "Edit users"),
        ("delete_user",           "Delete users"),
        ("manage_roles",          "Manage roles & permissions"),
    ],
    "Reports & Data": [
        ("view_reports",          "View reports (own data)"),
        ("view_all_reports",      "View reports (all users)"),
        ("export_data",           "Export data to CSV/Excel"),
        ("view_audit_log",        "View audit log"),
    ],
    "System": [
        ("manage_settings",       "Manage global settings"),
        ("manage_notifications",  "Manage notification settings"),
        ("manage_branding",       "Change branding & labels"),
        ("build_pipelines",       "Build pipeline templates"),
        ("danger_zone",           "Danger zone (wipe, reset)"),
    ],
}


# ── Workers ───────────────────────────────────────────────────────────────────

class LoadRolesWorker(QThread):
    done  = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            from firebase_client import firebase
            custom = firebase.get_collection("roles")
            # Merge with built-in roles
            built_in = [
                {"id": r, "name": r.title(), "built_in": True,
                 "permissions": DEFAULT_PERMISSIONS.get(r, [])}
                for r in ("admin", "manager", "technical")
            ]
            for cr in custom:
                built_in.append({**cr, "built_in": False})
            self.done.emit(built_in)
        except Exception as e:
            self.error.emit(str(e))


class SaveRoleWorker(QThread):
    done  = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, role: dict):
        super().__init__()
        self.role = role

    def run(self):
        try:
            from firebase_client import firebase
            rid = self.role.get("id", "")
            if rid and not self.role.get("built_in"):
                firebase.update_document("roles", rid, self.role)
            elif self.role.get("built_in"):
                # Save built-in role overrides
                firebase.create_document("role_overrides", self.role,
                                         doc_id=self.role["id"])
            else:
                firebase.create_document("roles", self.role)
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))


class DeleteRoleWorker(QThread):
    done  = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, role_id: str):
        super().__init__()
        self.role_id = role_id

    def run(self):
        try:
            from firebase_client import firebase
            firebase.delete_document("roles", self.role_id)
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))


# ── Permission checklist widget ───────────────────────────────────────────────

class PermissionChecklist(QWidget):
    def __init__(self, selected: list = None, parent=None):
        super().__init__(parent)
        self._checks: dict[str, QCheckBox] = {}
        self._build_ui(selected or [])

    def _build_ui(self, selected: list):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        for group_name, perms in ALL_PERMISSIONS.items():
            grp = QGroupBox(group_name)
            grp_lay = QVBoxLayout(grp)
            grp_lay.setSpacing(4)
            for perm_key, perm_label in perms:
                chk = QCheckBox(perm_label)
                chk.setChecked(perm_key in selected)
                self._checks[perm_key] = chk
                grp_lay.addWidget(chk)
            outer.addWidget(grp)

    def get_selected(self) -> list:
        return [k for k, chk in self._checks.items() if chk.isChecked()]

    def set_selected(self, selected: list):
        for k, chk in self._checks.items():
            chk.setChecked(k in selected)


# ── Role Editor Dialog ────────────────────────────────────────────────────────

class RoleEditorDialog(QDialog):
    saved = pyqtSignal()

    def __init__(self, role: dict = None, parent=None):
        super().__init__(parent)
        self.role    = role or {}
        self._worker = None
        self.setWindowTitle("Role Editor")
        self.setMinimumSize(520, 600)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        ttl = QLabel("🔑  Role Editor")
        ttl.setStyleSheet("font-size: 16px; font-weight: bold; color: #0F172A;")
        lay.addWidget(ttl)

        # Role name
        form = QFormLayout(); form.setSpacing(8)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Supervisor, L1 Support")
        self.name_input.setText(self.role.get("name", ""))
        self.name_input.setFixedHeight(36)
        if self.role.get("built_in"):
            self.name_input.setEnabled(False)
        form.addRow("Role Name *:", self.name_input)

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Short description (optional)")
        self.desc_input.setText(self.role.get("description", ""))
        self.desc_input.setFixedHeight(36)
        form.addRow("Description:", self.desc_input)
        lay.addLayout(form)

        if self.role.get("built_in"):
            note = QLabel("ℹ  This is a built-in role. Saving changes will override the default permissions.")
            note.setObjectName("info_label"); note.setWordWrap(True)
            lay.addWidget(note)

        # Permissions
        lay.addWidget(QLabel("Permissions:"))
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.checklist = PermissionChecklist(self.role.get("permissions", []))
        scroll.setWidget(self.checklist)
        lay.addWidget(scroll, 1)

        # Error + buttons
        self.err_lbl = QLabel(""); self.err_lbl.setObjectName("error_label"); self.err_lbl.setVisible(False)
        lay.addWidget(self.err_lbl)

        btn_row = QHBoxLayout()
        cancel   = QPushButton("Cancel"); cancel.setObjectName("btn_secondary"); cancel.clicked.connect(self.reject)
        self.save_btn = QPushButton("💾  Save Role"); self.save_btn.setObjectName("btn_primary")
        self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel); btn_row.addStretch(); btn_row.addWidget(self.save_btn)
        lay.addLayout(btn_row)

    def _save(self):
        name = self.name_input.text().strip()
        if not name:
            self.err_lbl.setText("⚠ Role name is required."); self.err_lbl.setVisible(True); return

        selected = self.checklist.get_selected()
        if not selected:
            self.err_lbl.setText("⚠ Select at least one permission."); self.err_lbl.setVisible(True); return

        role = dict(self.role)
        role["name"]        = name
        role["description"] = self.desc_input.text().strip()
        role["permissions"] = selected
        role["updated_at"]  = utc_now_iso()
        if not role.get("created_at"):
            role["created_at"] = utc_now_iso()

        self.save_btn.setEnabled(False); self.save_btn.setText("Saving…")
        self._worker = SaveRoleWorker(role)
        self._worker.done.connect(lambda: (self.saved.emit(), self.accept()))
        self._worker.error.connect(lambda e: (
            self.err_lbl.setText(f"⚠ {e}"), self.err_lbl.setVisible(True),
            self.save_btn.setEnabled(True), self.save_btn.setText("💾  Save Role")
        ))
        self._worker.start()


# ── Role Builder Panel ────────────────────────────────────────────────────────

class RoleBuilderPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._roles: list[dict] = []
        self._worker = None
        self._build_ui()
        self._load()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        hdr = QHBoxLayout()
        ttl = QLabel("Roles & Permissions"); ttl.setObjectName("section_title"); hdr.addWidget(ttl); hdr.addStretch()
        new_btn = QPushButton("+ New Role"); new_btn.setObjectName("btn_primary")
        new_btn.clicked.connect(self._new_role); hdr.addWidget(new_btn)
        lay.addLayout(hdr)

        info = QLabel("Built-in roles can have permissions overridden. Custom roles can be created for specific use cases.")
        info.setObjectName("info_label"); info.setWordWrap(True); lay.addWidget(info)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 0, 0)
        self.role_list = QListWidget(); self.role_list.setMinimumWidth(200)
        self.role_list.currentRowChanged.connect(self._on_select)
        ll.addWidget(self.role_list); splitter.addWidget(left)

        right = QWidget()
        right.setStyleSheet("background: white; border-radius: 8px; border: 1px solid #E2E8F0;")
        self.detail_lay = QVBoxLayout(right); self.detail_lay.setContentsMargins(16, 16, 16, 16)
        self._placeholder = QLabel("← Select a role to view permissions")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter); self._placeholder.setObjectName("info_label")
        self.detail_lay.addWidget(self._placeholder)
        self._detail_widgets = [self._placeholder]
        splitter.addWidget(right)

        splitter.setSizes([210, 460])
        lay.addWidget(splitter, 1)

    def _load(self):
        self._worker = LoadRolesWorker()
        self._worker.done.connect(self._on_loaded)
        self._worker.error.connect(lambda e: None)
        self._worker.start()

    @pyqtSlot(list)
    def _on_loaded(self, roles: list):
        self._roles = roles
        self.role_list.clear()
        for r in roles:
            tag  = " (built-in)" if r.get("built_in") else ""
            item = QListWidgetItem(f"  {r.get('name','?')}{tag}")
            item.setData(Qt.ItemDataRole.UserRole, r)
            self.role_list.addItem(item)

    def _on_select(self, row: int):
        if 0 <= row < len(self._roles):
            self._show_detail(self._roles[row])

    def _show_detail(self, role: dict):
        for w in self._detail_widgets:
            self.detail_lay.removeWidget(w); w.deleteLater()
        self._detail_widgets.clear()

        def add(w):
            self.detail_lay.addWidget(w); self._detail_widgets.append(w)

        name = QLabel(role.get("name", "—"))
        name.setStyleSheet("font-size: 16px; font-weight: bold; color: #0F172A;")
        add(name)

        if role.get("description"):
            d = QLabel(role["description"]); d.setObjectName("info_label")
            add(d)

        perms = role.get("permissions", [])
        perm_lbl = QLabel(f"Permissions: {len(perms)}")
        perm_lbl.setStyleSheet("font-size: 12px; color: #64748B; margin-top: 8px;")
        add(perm_lbl)

        # Show permission groups
        for group_name, group_perms in ALL_PERMISSIONS.items():
            matched = [(k, l) for k, l in group_perms if k in perms]
            if not matched:
                continue
            grp = QGroupBox(group_name); gl = QVBoxLayout(grp); gl.setSpacing(2)
            for _, lbl in matched:
                l = QLabel(f"  ✓  {lbl}"); l.setStyleSheet("font-size: 12px; color: #374151;")
                gl.addWidget(l)
            add(grp)

        spacer = QLabel(""); add(spacer)

        btn_row = QHBoxLayout(); bc = QWidget(); bc.setLayout(btn_row)
        edit_btn = QPushButton("✏ Edit Permissions"); edit_btn.setObjectName("btn_primary")
        edit_btn.clicked.connect(lambda _, r=role: self._edit_role(r))
        btn_row.addWidget(edit_btn)

        if not role.get("built_in"):
            del_btn = QPushButton("🗑 Delete"); del_btn.setObjectName("btn_danger")
            del_btn.clicked.connect(lambda _, r=role: self._delete_role(r))
            btn_row.addWidget(del_btn)

        btn_row.addStretch()
        add(bc)
        self.detail_lay.addStretch()

    def _new_role(self):
        dlg = RoleEditorDialog(parent=self)
        dlg.saved.connect(self._load)
        dlg.exec()

    def _edit_role(self, role: dict):
        dlg = RoleEditorDialog(role=role, parent=self)
        dlg.saved.connect(self._load)
        dlg.exec()

    def _delete_role(self, role: dict):
        if QMessageBox.question(self, "Delete Role",
            f"Delete role '{role.get('name')}'?\nUsers with this role will need to be reassigned.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        w = DeleteRoleWorker(role.get("id", ""))
        w.done.connect(self._load)
        w.error.connect(lambda e: QMessageBox.critical(self, "Error", e))
        w.start()
