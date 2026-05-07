# ui/admin_dashboard.py
"""
Admin Dashboard — God Mode.
Tabs: Users | All SRs | Pipeline Builder | Roles | Statistics | Settings | Audit Log
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QLineEdit, QComboBox, QDialog, QFormLayout, QMessageBox,
    QTextEdit, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import QColor, QFont

from firebase_client import firebase, FirebaseAuthError, FirebaseNetworkError
from utils.auth import session, DEFAULT_PERMISSIONS
from utils.helpers import (
    format_datetime, role_badge_color, status_color,
    utc_now_iso, validate_email, validate_password, truncate
)
from ui.admin_settings  import AdminSettingsPanel
from ui.pipeline_builder import PipelineBuilderPanel
from ui.role_builder    import RoleBuilderPanel
from ui.stats_panel     import StatsPanel


# ── Workers ───────────────────────────────────────────────────────────────────

class LoadAllWorker(QThread):
    done  = pyqtSignal(list, list, list)   # users, srs, audit
    error = pyqtSignal(str)

    def run(self):
        try:
            users = firebase.get_collection("users")
            srs   = firebase.get_collection("service_requests")
            audit = firebase.get_collection("audit_log")
            self.done.emit(users, srs, audit)
        except Exception as e:
            self.error.emit(str(e))


class CreateUserWorker(QThread):
    done  = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, email, password, name, role, whatsapp):
        super().__init__()
        self.email = email; self.password = password
        self.name  = name;  self.role = role; self.whatsapp = whatsapp

    def run(self):
        try:
            uid = firebase.create_user(self.email, self.password)
            firebase.create_document("users", {
                "uid":              uid,
                "email":            self.email,
                "name":             self.name,
                "role":             self.role,
                "whatsapp_number":  self.whatsapp,
                "active":           True,
                "created_at":       utc_now_iso(),
            }, doc_id=uid)
            from services.audit_service import log_action
            log_action("user_created", f"Created {self.email} ({self.role})", uid)
            self.done.emit()
        except (FirebaseAuthError, FirebaseNetworkError) as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Failed: {e}")


class UpdateUserWorker(QThread):
    done  = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, uid, data):
        super().__init__()
        self.uid  = uid
        self.data = data

    def run(self):
        try:
            self.data["updated_at"] = utc_now_iso()
            firebase.update_document("users", self.uid, self.data)
            from services.audit_service import log_action
            log_action("user_updated", str(self.data), self.uid)
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))


# ── Create User Dialog ────────────────────────────────────────────────────────

class CreateUserDialog(QDialog):
    user_created = pyqtSignal()

    def __init__(self, roles: list, parent=None):
        super().__init__(parent)
        self.roles = roles
        self.setWindowTitle("Create New User")
        self.setFixedSize(440, 420)
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12); lay.setContentsMargins(24, 24, 24, 24)

        ttl = QLabel("👤  Create New User")
        ttl.setStyleSheet("font-size: 16px; font-weight: bold; color: #0F172A;")
        lay.addWidget(ttl)

        form = QFormLayout(); form.setSpacing(10)

        self.name_input     = QLineEdit(); self.name_input.setPlaceholderText("Full name"); self.name_input.setFixedHeight(36)
        self.email_input    = QLineEdit(); self.email_input.setPlaceholderText("email@company.com"); self.email_input.setFixedHeight(36)
        self.pwd_input      = QLineEdit(); self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password); self.pwd_input.setPlaceholderText("Min. 6 chars"); self.pwd_input.setFixedHeight(36)
        self.whatsapp_input = QLineEdit(); self.whatsapp_input.setPlaceholderText("+91XXXXXXXXXX (optional)"); self.whatsapp_input.setFixedHeight(36)

        self.role_combo = QComboBox(); self.role_combo.setFixedHeight(36)
        for r in self.roles:
            self.role_combo.addItem(r.get("name", r.get("id", "?")), r.get("id", r.get("name","")))

        form.addRow("Full Name *",  self.name_input)
        form.addRow("Email *",      self.email_input)
        form.addRow("Password *",   self.pwd_input)
        form.addRow("WhatsApp No.", self.whatsapp_input)
        form.addRow("Role *",       self.role_combo)
        lay.addLayout(form)

        self.err_lbl = QLabel(""); self.err_lbl.setObjectName("error_label"); self.err_lbl.setVisible(False); lay.addWidget(self.err_lbl)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancel"); cancel.setObjectName("btn_secondary"); cancel.clicked.connect(self.reject)
        self.create_btn = QPushButton("Create User"); self.create_btn.setObjectName("btn_primary"); self.create_btn.clicked.connect(self._submit)
        btn_row.addWidget(cancel); btn_row.addWidget(self.create_btn)
        lay.addLayout(btn_row)

    def _submit(self):
        name  = self.name_input.text().strip()
        email = self.email_input.text().strip()
        pwd   = self.pwd_input.text()
        wa    = self.whatsapp_input.text().strip()
        role  = self.role_combo.currentData()

        if not name: return self._show_err("Full name is required.")
        if not validate_email(email): return self._show_err("Enter a valid email.")
        ok, msg = validate_password(pwd)
        if not ok: return self._show_err(msg)

        self.create_btn.setEnabled(False); self.create_btn.setText("Creating…")
        self._worker = CreateUserWorker(email, pwd, name, role, wa)
        self._worker.done.connect(lambda: (self.user_created.emit(), self.accept()))
        self._worker.error.connect(self._on_err)
        self._worker.start()

    def _on_err(self, msg):
        self.create_btn.setEnabled(True); self.create_btn.setText("Create User")
        self._show_err(msg)

    def _show_err(self, msg):
        self.err_lbl.setText(f"⚠ {msg}"); self.err_lbl.setVisible(True)


# ── Admin Dashboard ───────────────────────────────────────────────────────────

class AdminDashboard(QWidget):
    logout_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._users:  list = []
        self._srs:    list = []
        self._audit:  list = []
        self._roles:  list = []
        self._poll_timer = QTimer(); self._poll_timer.setInterval(3000)
        self._poll_timer.timeout.connect(self._refresh_all)
        self._workers: list = []
        self._settings_panel = None
        self._build_ui()

    def start_polling(self):
        self._refresh_all(); self._poll_timer.start()

    def stop_polling(self):
        self._poll_timer.stop()

    def _build_ui(self):
        root = QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────────────
        sidebar = QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(230)
        sb = QVBoxLayout(sidebar); sb.setContentsMargins(0,20,0,20); sb.setSpacing(4)

        brand = QLabel("🛠  SR Manager")
        brand.setStyleSheet("color:white;font-size:15px;font-weight:bold;padding:0 20px;margin-bottom:8px;")
        sb.addWidget(brand)

        role_lbl = QLabel(f"Admin  •  {session.name}")
        role_lbl.setStyleSheet("color:#94A3B8;font-size:11px;padding:0 20px;margin-bottom:16px;")
        sb.addWidget(role_lbl)

        tabs = [
            ("nav_users",     "👥  Users"),
            ("nav_srs",       "📋  All SRs"),
            ("nav_pipeline",  "🔧  Pipelines"),
            ("nav_roles",     "🔑  Roles"),
            ("nav_stats",     "📊  Statistics"),
            ("nav_settings",  "⚙️  Settings"),
            ("nav_audit",     "📜  Audit Log"),
        ]
        self._nav_btns = {}
        for attr, label in tabs:
            btn = QPushButton(label); btn.setObjectName("sidebar_nav"); btn.setCheckable(True)
            setattr(self, attr + "_btn", btn)
            self._nav_btns[attr] = btn
            sb.addWidget(btn)

        # Connect nav
        self.nav_users_btn.setChecked(True)
        idx_map = {attr: i for i, (attr, _) in enumerate(tabs)}
        for attr, _ in tabs:
            i = idx_map[attr]
            self._nav_btns[attr].clicked.connect(lambda _, n=i: self._switch_tab(n))

        sb.addStretch()
        self.sync_lbl = QLabel("● Live"); self.sync_lbl.setStyleSheet("color:#10B981;font-size:11px;padding:0 20px;")
        sb.addWidget(self.sync_lbl)

        logout_btn = QPushButton("🚪  Log Out")
        logout_btn.setStyleSheet("QPushButton{background:transparent;color:#94A3B8;border:none;text-align:left;padding:10px 20px;font-size:13px;}QPushButton:hover{color:#EF4444;}")
        logout_btn.clicked.connect(self._logout)
        sb.addWidget(logout_btn)
        root.addWidget(sidebar)

        # ── Content ───────────────────────────────────────────────────────────
        self.content = QWidget(); self.content.setStyleSheet("background:#F1F5F9;")
        self.content_lay = QVBoxLayout(self.content)
        self.content_lay.setContentsMargins(24,24,24,24)

        self._build_users_tab()
        self._build_srs_tab()

        self.pipeline_tab = PipelineBuilderPanel()
        self.content_lay.addWidget(self.pipeline_tab); self.pipeline_tab.setVisible(False)

        self.roles_tab = RoleBuilderPanel()
        self.content_lay.addWidget(self.roles_tab); self.roles_tab.setVisible(False)

        self.stats_tab = StatsPanel()
        self.content_lay.addWidget(self.stats_tab); self.stats_tab.setVisible(False)

        self._settings_panel = AdminSettingsPanel()
        self._settings_panel.stylesheet_changed.connect(self._apply_style)
        self.content_lay.addWidget(self._settings_panel); self._settings_panel.setVisible(False)

        self._build_audit_tab()

        root.addWidget(self.content)

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def _build_users_tab(self):
        self.users_tab = QWidget()
        lay = QVBoxLayout(self.users_tab); lay.setSpacing(16); lay.setContentsMargins(0,0,0,0)

        hdr = QHBoxLayout()
        ttl = QLabel("User Management"); ttl.setObjectName("section_title"); hdr.addWidget(ttl); hdr.addStretch()
        self.create_user_btn = QPushButton("+ Create User"); self.create_user_btn.setObjectName("btn_primary")
        self.create_user_btn.clicked.connect(self._open_create_user); hdr.addWidget(self.create_user_btn)
        lay.addLayout(hdr)

        # Stats row
        stats = QHBoxLayout()
        self.stat_total   = self._stat_card("Total Users", "—", "#3B82F6")
        self.stat_admins  = self._stat_card("Admins",      "—", "#EF4444")
        self.stat_mgrs    = self._stat_card("Managers",    "—", "#8B5CF6")
        self.stat_techs   = self._stat_card("Technicals",  "—", "#06B6D4")
        for c in (self.stat_total, self.stat_admins, self.stat_mgrs, self.stat_techs):
            stats.addWidget(c)
        lay.addLayout(stats)

        self.users_table = QTableWidget()
        self.users_table.setColumnCount(6)
        self.users_table.setHorizontalHeaderLabels(["Name", "Email", "Role", "WhatsApp", "Created", "Actions"])
        self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.users_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.users_table.setColumnWidth(5, 200)
        self.users_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.users_table.verticalHeader().setVisible(False)
        self.users_table.setAlternatingRowColors(True)
        lay.addWidget(self.users_table)
        self.content_lay.addWidget(self.users_tab)

    def _build_srs_tab(self):
        self.srs_tab = QWidget(); self.srs_tab.setVisible(False)
        lay = QVBoxLayout(self.srs_tab); lay.setSpacing(16); lay.setContentsMargins(0,0,0,0)

        hdr = QHBoxLayout()
        ttl = QLabel("All Service Requests"); ttl.setObjectName("section_title"); hdr.addWidget(ttl); hdr.addStretch()
        lay.addLayout(hdr)

        self.srs_table = QTableWidget()
        self.srs_table.setColumnCount(7)
        self.srs_table.setHorizontalHeaderLabels(
            ["Title", "Type", "Status", "Priority", "Pipeline", "Assigned To", "Created"])
        self.srs_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.srs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.srs_table.verticalHeader().setVisible(False)
        self.srs_table.setAlternatingRowColors(True)
        lay.addWidget(self.srs_table)
        self.content_lay.addWidget(self.srs_tab)

    def _build_audit_tab(self):
        self.audit_tab = QWidget(); self.audit_tab.setVisible(False)
        lay = QVBoxLayout(self.audit_tab); lay.setSpacing(16); lay.setContentsMargins(0,0,0,0)

        ttl = QLabel("Audit Log"); ttl.setObjectName("section_title"); lay.addWidget(ttl)

        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(6)
        self.audit_table.setHorizontalHeaderLabels(
            ["Timestamp", "Actor", "Role", "Action", "Details", "Target"])
        self.audit_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.audit_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.audit_table.verticalHeader().setVisible(False)
        self.audit_table.setAlternatingRowColors(True)
        lay.addWidget(self.audit_table)
        self.content_lay.addWidget(self.audit_tab)

    def _stat_card(self, label, value, color):
        card = QFrame(); card.setObjectName("stat_card")
        card.setStyleSheet(f"QFrame#stat_card{{background:white;border-radius:10px;border:1px solid #E2E8F0;border-top:4px solid {color};}}")
        lay = QVBoxLayout(card); lay.setContentsMargins(14,12,14,12); lay.setSpacing(3)
        val = QLabel(value); val.setStyleSheet(f"font-size:26px;font-weight:bold;color:{color};")
        lbl = QLabel(label); lbl.setStyleSheet("font-size:12px;color:#64748B;")
        lay.addWidget(val); lay.addWidget(lbl)
        card._val_label = val
        return card

    def _switch_tab(self, idx: int):
        tabs = [self.users_tab, self.srs_tab, self.pipeline_tab, self.roles_tab,
                self.stats_tab, self._settings_panel, self.audit_tab]
        for i, tab in enumerate(tabs):
            tab.setVisible(i == idx)
        for i, (attr, _) in enumerate([
            ("nav_users",""), ("nav_srs",""), ("nav_pipeline",""), ("nav_roles",""),
            ("nav_stats",""), ("nav_settings",""), ("nav_audit","")
        ]):
            self._nav_btns[attr].setChecked(i == idx)

    # ── Data refresh ──────────────────────────────────────────────────────────

    def _refresh_all(self):
        w = LoadAllWorker()
        w.done.connect(self._on_data_loaded)
        w.error.connect(self._on_error)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w); w.start()

    @pyqtSlot(list, list, list)
    def _on_data_loaded(self, users: list, srs: list, audit: list):
        self._users = users; self._srs = srs; self._audit = audit
        self.sync_lbl.setText("● Live")
        self.sync_lbl.setStyleSheet("color:#10B981;font-size:11px;padding:0 20px;")

        # Build roles list for combos
        self._roles = [
            {"id": r, "name": r.title()}
            for r in ("admin", "manager", "technical")
        ]
        try:
            custom = firebase.get_collection("roles")
            self._roles.extend(custom)
        except Exception:
            pass

        self._populate_users(users)
        self._populate_srs(srs, users)
        self._populate_audit(audit)
        self.stats_tab.populate_user_filter(users)

        # KPI cards
        self.stat_total._val_label.setText(str(len(users)))
        self.stat_admins._val_label.setText(str(sum(1 for u in users if u.get("role") == "admin")))
        self.stat_mgrs._val_label.setText(str(sum(1 for u in users if u.get("role") == "manager")))
        self.stat_techs._val_label.setText(str(sum(1 for u in users if u.get("role") == "technical")))

    def _populate_users(self, users: list):
        self.users_table.setRowCount(len(users))
        for row, u in enumerate(users):
            role = u.get("role", "technical")
            cells = [u.get("name","—"), u.get("email","—"), role,
                     u.get("whatsapp_number","—"), format_datetime(u.get("created_at"))]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if col == 2:
                    item.setForeground(QColor(role_badge_color(role)))
                    item.setFont(QFont("", -1, QFont.Weight.Bold))
                self.users_table.setItem(row, col, item)

            # Actions cell
            cell_w = QWidget(); cl = QHBoxLayout(cell_w)
            cl.setContentsMargins(4,2,4,2); cl.setSpacing(4)

            role_combo = QComboBox(); role_combo.setFixedHeight(28)
            for r in self._roles:
                role_combo.addItem(r.get("name","?"), r.get("id",""))
            role_combo.setCurrentText(role.title())

            save_btn = QPushButton("Save"); save_btn.setFixedHeight(28); save_btn.setFixedWidth(50)
            save_btn.setStyleSheet("QPushButton{background:#3B82F6;color:white;border:none;border-radius:4px;font-size:11px;font-weight:bold;}QPushButton:hover{background:#2563EB;}")
            uid = u.get("uid", u.get("id",""))
            save_btn.clicked.connect(lambda _, u=uid, c=role_combo: self._save_role(u, c.currentData()))

            suspend_btn = QPushButton("🚫"); suspend_btn.setFixedSize(28,28)
            is_active = u.get("active", True)
            suspend_btn.setToolTip("Suspend" if is_active else "Activate")
            suspend_btn.setStyleSheet(f"QPushButton{{background:{'#EF4444' if is_active else '#10B981'};color:white;border:none;border-radius:4px;font-size:11px;}}QPushButton:hover{{opacity:0.8;}}")
            suspend_btn.clicked.connect(lambda _, u=uid, a=is_active: self._toggle_suspend(u, a))

            cl.addWidget(role_combo); cl.addWidget(save_btn); cl.addWidget(suspend_btn)
            self.users_table.setCellWidget(row, 5, cell_w)
            self.users_table.setRowHeight(row, 44)

    def _populate_srs(self, srs: list, users: list):
        user_map = {u.get("uid", u.get("id","")): u.get("name","?") for u in users}
        self.srs_table.setRowCount(len(srs))
        for row, sr in enumerate(srs):
            status   = sr.get("status","open")
            ps       = sr.get("pipeline_state")
            pipe_lbl = ps.get("template_name","—") if isinstance(ps, dict) else "—"
            cells    = [
                truncate(sr.get("title","—"), 40),
                sr.get("type","—").replace("_"," ").title(),
                status.replace("_"," ").title(),
                sr.get("priority","medium").capitalize(),
                pipe_lbl,
                user_map.get(sr.get("assigned_to",""), "Unassigned"),
                format_datetime(sr.get("created_at")),
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if col == 2:
                    item.setForeground(QColor(status_color(status)))
                    item.setFont(QFont("", -1, QFont.Weight.Bold))
                self.srs_table.setItem(row, col, item)
            self.srs_table.setRowHeight(row, 40)

    def _populate_audit(self, audit: list):
        sorted_audit = sorted(audit, key=lambda x: x.get("timestamp",""), reverse=True)
        self.audit_table.setRowCount(len(sorted_audit))
        for row, entry in enumerate(sorted_audit):
            cells = [
                format_datetime(entry.get("timestamp")),
                entry.get("actor_name","—"),
                entry.get("actor_role","—"),
                entry.get("action","—"),
                truncate(entry.get("details","—"), 50),
                truncate(entry.get("target_id","—"), 20),
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.audit_table.setItem(row, col, item)
            self.audit_table.setRowHeight(row, 36)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _open_create_user(self):
        dlg = CreateUserDialog(self._roles, self)
        dlg.user_created.connect(self._refresh_all)
        dlg.exec()

    def _save_role(self, uid: str, role: str):
        w = UpdateUserWorker(uid, {"role": role})
        w.done.connect(self._refresh_all)
        w.error.connect(lambda msg: QMessageBox.critical(self, "Error", msg))
        self._workers.append(w); w.start()

    def _toggle_suspend(self, uid: str, currently_active: bool):
        new_state = not currently_active
        label     = "activate" if new_state else "suspend"
        if QMessageBox.question(self, f"{'Activate' if new_state else 'Suspend'} User",
            f"Are you sure you want to {label} this user?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        w = UpdateUserWorker(uid, {"active": new_state})
        w.done.connect(self._refresh_all)
        w.error.connect(lambda msg: QMessageBox.critical(self, "Error", msg))
        self._workers.append(w); w.start()

    def _apply_style(self, new_style: str):
        QApplication.instance().setStyleSheet(new_style)

    def _on_error(self, msg: str):
        self.sync_lbl.setText("⚠ Sync Error")
        self.sync_lbl.setStyleSheet("color:#EF4444;font-size:11px;padding:0 20px;")

    def _logout(self):
        self.stop_polling(); firebase.logout(); self.logout_requested.emit()
