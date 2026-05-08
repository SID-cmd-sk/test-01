# ui/manager_dashboard.py
"""
Manager Dashboard:
- View all SRs with technician availability shown inline
- Create & assign SRs (pick template or freeform)
- Monitor pipeline step progress
- Real-time polling
- Statistics tab (team scope)
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QLineEdit, QComboBox, QDialog, QFormLayout, QMessageBox,
    QTextEdit, QGroupBox, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import QColor, QFont

from db import storage
from utils.auth import session
from utils.helpers import (
    format_datetime, status_color, utc_now_iso,
    validate_required, truncate, availability_color
)
from ui.stats_panel import StatsPanel
from services.pipeline_service import pipeline_service


# ── Workers ───────────────────────────────────────────────────────────────────

class LoadDataWorker(QThread):
    done  = pyqtSignal(list, list, list)   # srs, users, templates
    error = pyqtSignal(str)

    def run(self):
        try:
            srs       = storage.get_collection("service_requests")
            users     = storage.get_collection("users")
            templates = pipeline_service.get_templates()
            self.done.emit(srs, users, templates)
        except Exception as e:
            self.error.emit(str(e))


class CreateSRWorker(QThread):
    done  = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, data: dict):
        super().__init__(); self.data = data

    def run(self):
        try:
            storage.create_document("service_requests", self.data)
            from services.audit_service import log_action
            log_action("sr_created", self.data.get("title",""), "")
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))


class UpdateSRWorker(QThread):
    done  = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, sr_id: str, updates: dict):
        super().__init__(); self.sr_id = sr_id; self.updates = updates

    def run(self):
        try:
            storage.update_document("service_requests", self.sr_id, self.updates)
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))


class SyncNowWorker(QThread):
    done = pyqtSignal(dict)

    def run(self):
        # Offline mode — no sync needed
        self.done.emit({"ok": True, "message": "Offline mode: all data saved locally."})


# ── Create SR Dialog ──────────────────────────────────────────────────────────

class CreateSRDialog(QDialog):
    sr_created = pyqtSignal()

    def __init__(self, users: list, templates: list, srs: list, parent=None):
        super().__init__(parent)
        self.users     = users
        self.templates = templates
        self.srs       = srs
        self.setWindowTitle("Create Service Request")
        self.setMinimumSize(540, 560)
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setSpacing(12); lay.setContentsMargins(24,24,24,24)

        ttl = QLabel("📋  Create Service Request")
        ttl.setStyleSheet("font-size:16px;font-weight:bold;color:#0F172A;")
        lay.addWidget(ttl)

        form = QFormLayout(); form.setSpacing(10); form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.title_input = QLineEdit(); self.title_input.setPlaceholderText("Short descriptive title"); self.title_input.setFixedHeight(36)
        self.desc_input  = QTextEdit(); self.desc_input.setPlaceholderText("Detailed description…"); self.desc_input.setFixedHeight(90)

        # Pipeline template selector
        self.tpl_combo = QComboBox(); self.tpl_combo.setFixedHeight(36)
        self.tpl_combo.addItem("— No Template (Freeform) —", None)
        for t in self.templates:
            steps = len(t.get("steps", []))
            self.tpl_combo.addItem(f"{t.get('name','?')}  ({steps} steps)", t)
        self.tpl_combo.currentIndexChanged.connect(self._on_template_change)

        # Assign to — with availability indicator
        self.assign_combo = QComboBox(); self.assign_combo.setFixedHeight(36)
        self.assign_combo.addItem("— Unassigned —", "")

        # Compute active SRs per user
        active_counts = {}
        for sr in self.srs:
            if sr.get("status") in ("open","in_progress"):
                uid = sr.get("assigned_to","")
                active_counts[uid] = active_counts.get(uid, 0) + 1

        for u in self.users:
            if u.get("role") in ("technical","manager"):
                uid   = u.get("uid", u.get("id",""))
                name  = u.get("name", u.get("email", uid))
                count = active_counts.get(uid, 0)
                _, avail = availability_color(count)
                self.assign_combo.addItem(f"{avail}  {name}  ({count} active)", uid)

        self.priority_combo = QComboBox(); self.priority_combo.addItems(["low","medium","high"])
        self.priority_combo.setCurrentText("medium"); self.priority_combo.setFixedHeight(36)

        form.addRow("Title *",       self.title_input)
        form.addRow("Description *", self.desc_input)
        form.addRow("Template",      self.tpl_combo)
        form.addRow("Assign To",     self.assign_combo)
        form.addRow("Priority",      self.priority_combo)
        lay.addLayout(form)

        # Template steps preview
        self.steps_preview = QLabel("")
        self.steps_preview.setObjectName("info_label")
        self.steps_preview.setWordWrap(True)
        lay.addWidget(self.steps_preview)

        self.err_lbl = QLabel(""); self.err_lbl.setObjectName("error_label"); self.err_lbl.setVisible(False)
        lay.addWidget(self.err_lbl)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancel"); cancel.setObjectName("btn_secondary"); cancel.clicked.connect(self.reject)
        self.submit_btn = QPushButton("Create SR"); self.submit_btn.setObjectName("btn_primary"); self.submit_btn.clicked.connect(self._submit)
        btn_row.addWidget(cancel); btn_row.addWidget(self.submit_btn)
        lay.addLayout(btn_row)

    def _on_template_change(self):
        tpl = self.tpl_combo.currentData()
        if not tpl:
            self.steps_preview.setText("")
            return
        steps = tpl.get("steps", [])
        lines = [f"  {i+1}. {s.get('name','?')}  →  {s.get('approver_role','?')}"
                 for i, s in enumerate(steps)]
        self.steps_preview.setText("Steps:\n" + "\n".join(lines))

    def _submit(self):
        title = self.title_input.text().strip()
        desc  = self.desc_input.toPlainText().strip()
        ok, msg = validate_required(title, "Title")
        if not ok: return self._show_err(msg)
        ok, msg = validate_required(desc, "Description")
        if not ok: return self._show_err(msg)

        assigned_uid = self.assign_combo.currentData()
        template     = self.tpl_combo.currentData()
        now          = utc_now_iso()

        data = {
            "title":       title,
            "description": desc,
            "created_by":  session.uid,
            "assigned_to": assigned_uid or "",
            "type":        "manager_assigned" if assigned_uid else "unassigned",
            "status":      "open",
            "priority":    self.priority_combo.currentText(),
            "created_at":  now,
            "updated_at":  now,
        }

        if template:
            data["pipeline_state"] = pipeline_service.init_pipeline_state(template)

        self.submit_btn.setEnabled(False); self.submit_btn.setText("Creating…")
        self._worker = CreateSRWorker(data)
        self._worker.done.connect(lambda: (self.sr_created.emit(), self.accept()))
        self._worker.error.connect(lambda e: (
            self.err_lbl.setText(f"⚠ {e}"), self.err_lbl.setVisible(True),
            self.submit_btn.setEnabled(True), self.submit_btn.setText("Create SR")
        ))
        self._worker.start()

    def _show_err(self, msg):
        self.err_lbl.setText(f"⚠ {msg}"); self.err_lbl.setVisible(True)


# ── SR Detail Dialog (with pipeline view) ─────────────────────────────────────

class SRDetailDialog(QDialog):
    sr_updated = pyqtSignal()

    def __init__(self, sr: dict, users: list, parent=None):
        super().__init__(parent)
        self.sr    = sr
        self.users = users
        self.setWindowTitle(f"SR — {sr.get('title','')}")
        self.setMinimumSize(560, 520)
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setSpacing(12); lay.setContentsMargins(24,24,24,24)

        ttl = QLabel(self.sr.get("title","—"))
        ttl.setStyleSheet("font-size:16px;font-weight:bold;color:#0F172A;"); ttl.setWordWrap(True)
        lay.addWidget(ttl)

        status = self.sr.get("status","open")
        s_lbl  = QLabel(status.replace("_"," ").upper())
        s_lbl.setStyleSheet(f"color:white;background:{status_color(status)};border-radius:4px;padding:2px 10px;font-size:11px;font-weight:bold;")
        p_lbl  = QLabel(self.sr.get("priority","medium").capitalize())
        p_lbl.setStyleSheet("color:#92400E;background:#FEF3C7;border-radius:4px;padding:2px 10px;font-size:11px;font-weight:bold;")
        meta   = QHBoxLayout(); meta.addWidget(s_lbl); meta.addWidget(p_lbl); meta.addStretch()
        lay.addLayout(meta)

        desc_grp = QGroupBox("Description"); dl = QVBoxLayout(desc_grp)
        d = QLabel(self.sr.get("description","—")); d.setWordWrap(True)
        dl.addWidget(d); lay.addWidget(desc_grp)

        # Pipeline steps (if any)
        ps = self.sr.get("pipeline_state")
        if isinstance(ps, dict) and ps.get("steps_state"):
            pipe_grp = QGroupBox(f"Pipeline: {ps.get('template_name','?')}  —  Step {ps.get('current_step',0)+1} of {ps.get('total_steps',0)}")
            pl = QVBoxLayout(pipe_grp)
            current_idx = ps.get("current_step", 0)
            for step in ps.get("steps_state", []):
                si    = step.get("index", 0)
                sstat = step.get("status","pending")
                if sstat == "done":
                    icon, color = "✅", "#10B981"
                elif sstat == "skipped":
                    icon, color = "⏭", "#F59E0B"
                elif si == current_idx:
                    icon, color = "▶", "#3B82F6"
                else:
                    icon, color = "○", "#94A3B8"

                sf = QLabel(f"{icon}  Step {si+1}: {step.get('name','?')}  "
                            f"[{step.get('approver_role','?')}]"
                            + (f"  — {step.get('skip_reason','')}" if sstat=="skipped" else ""))
                sf.setStyleSheet(f"color:{color};font-size:12px;padding:2px 0;")
                pl.addWidget(sf)
            lay.addWidget(pipe_grp)

        # Assignment
        ag = QGroupBox("Assignment"); af = QFormLayout(ag)
        user_map = {u.get("uid",u.get("id","")): u for u in self.users}

        self.assign_combo = QComboBox(); self.assign_combo.setFixedHeight(34)
        self.assign_combo.addItem("— Unassigned —", "")
        active_counts = {}
        cur = self.sr.get("assigned_to","")
        for u in self.users:
            if u.get("role") in ("technical","manager"):
                uid = u.get("uid",u.get("id",""))
                name = u.get("name","?")
                _, avail = availability_color(active_counts.get(uid,0))
                self.assign_combo.addItem(f"{avail}  {name}", uid)
        for i in range(self.assign_combo.count()):
            if self.assign_combo.itemData(i) == cur:
                self.assign_combo.setCurrentIndex(i); break

        creator = user_map.get(self.sr.get("created_by",""), {}).get("name","—")
        af.addRow("Assigned To:", self.assign_combo)
        af.addRow("Created By:",  QLabel(creator))
        af.addRow("Created At:",  QLabel(format_datetime(self.sr.get("created_at"))))
        af.addRow("Updated At:",  QLabel(format_datetime(self.sr.get("updated_at"))))
        lay.addWidget(ag)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Close"); cancel.setObjectName("btn_secondary"); cancel.clicked.connect(self.reject)
        save   = QPushButton("💾 Save Assignment"); save.setObjectName("btn_primary"); save.clicked.connect(self._save_assign)
        if status not in ("closed","completed"):
            close_sr = QPushButton("✅ Close SR"); close_sr.setObjectName("btn_success"); close_sr.clicked.connect(self._close_sr)
            btn_row.addWidget(close_sr)
        btn_row.addWidget(cancel); btn_row.addWidget(save)
        lay.addLayout(btn_row)

    def _save_assign(self):
        uid = self.assign_combo.currentData()
        self._update({"assigned_to": uid, "updated_at": utc_now_iso()}, "Assignment saved.")

    def _close_sr(self):
        if QMessageBox.question(self, "Close SR", "Close this service request?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self._update({"status":"closed","updated_at":utc_now_iso()}, "SR closed.")

    def _update(self, updates: dict, msg: str):
        self._worker = UpdateSRWorker(self.sr.get("id",""), updates)
        self._worker.done.connect(lambda: (
            QMessageBox.information(self, "Saved", msg),
            self.sr_updated.emit(), self.accept()
        ))
        self._worker.error.connect(lambda e: QMessageBox.critical(self, "Error", e))
        self._worker.start()


# ── Manager Dashboard ─────────────────────────────────────────────────────────

class ManagerDashboard(QWidget):
    logout_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._srs:       list = []
        self._users:     list = []
        self._templates: list = []
        self._filter     = "all"
        self._poll_timer = QTimer(); self._poll_timer.setInterval(3000)
        self._poll_timer.timeout.connect(self._refresh)
        self._workers: list = []
        self._build_ui()

    def start_polling(self): self._refresh(); self._poll_timer.start()
    def stop_polling(self):  self._poll_timer.stop()

    def _build_ui(self):
        root = QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # Sidebar
        sidebar = QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(230)
        sb = QVBoxLayout(sidebar); sb.setContentsMargins(0,20,0,20); sb.setSpacing(4)

        brand = QLabel("🛠  SR Manager"); brand.setStyleSheet("color:white;font-size:15px;font-weight:bold;padding:0 20px;margin-bottom:8px;")
        sb.addWidget(brand)
        sb.addWidget(self._role_lbl(f"Manager  •  {session.name}"))

        filters = [("all","📋  All SRs"),("open","🔵  Open"),
                   ("in_progress","🟡  In Progress"),("completed","🟢  Completed"),("closed","⚫  Closed")]
        self._nav_btns = []
        for val, label in filters:
            btn = QPushButton(label); btn.setObjectName("sidebar_nav"); btn.setCheckable(True)
            btn.clicked.connect(lambda _, v=val: self._set_filter(v))
            sb.addWidget(btn); self._nav_btns.append((val, btn))
        self._nav_btns[0][1].setChecked(True)

        # Stats tab button
        self.nav_stats_btn = QPushButton("📊  Statistics"); self.nav_stats_btn.setObjectName("sidebar_nav"); self.nav_stats_btn.setCheckable(True)
        self.nav_stats_btn.clicked.connect(self._show_stats)
        sb.addWidget(self.nav_stats_btn)

        sb.addStretch()
        sync_btn = QPushButton("💾  Save Status"); sync_btn.setObjectName("sidebar_nav"); sync_btn.clicked.connect(self._manual_sync)
        sb.addWidget(sync_btn)
        self.sync_lbl = QLabel("● Offline Mode"); self.sync_lbl.setStyleSheet("color:#10B981;font-size:11px;padding:0 20px;")
        sb.addWidget(self.sync_lbl)
        logout_btn = QPushButton("🚪  Log Out"); logout_btn.setStyleSheet("QPushButton{background:transparent;color:#94A3B8;border:none;text-align:left;padding:10px 20px;}QPushButton:hover{color:#EF4444;}")
        logout_btn.clicked.connect(self._logout); sb.addWidget(logout_btn)
        root.addWidget(sidebar)

        # Content
        self.content_stack = QWidget(); self.content_stack.setStyleSheet("background:#F1F5F9;")
        cl = QVBoxLayout(self.content_stack); cl.setContentsMargins(24,24,24,24); cl.setSpacing(16)

        # SR view
        self.sr_view = QWidget()
        sl = QVBoxLayout(self.sr_view); sl.setContentsMargins(0,0,0,0); sl.setSpacing(16)

        hdr = QHBoxLayout()
        self.page_title = QLabel("All Service Requests"); self.page_title.setObjectName("section_title"); hdr.addWidget(self.page_title); hdr.addStretch()
        create_btn = QPushButton("+ New SR"); create_btn.setObjectName("btn_primary"); create_btn.clicked.connect(self._open_create)
        hdr.addWidget(create_btn); sl.addLayout(hdr)

        # Stats cards
        stats_row = QHBoxLayout()
        self.stat_all    = self._stat("Total","—","#3B82F6")
        self.stat_open   = self._stat("Open","—","#F59E0B")
        self.stat_prog   = self._stat("In Progress","—","#8B5CF6")
        self.stat_done   = self._stat("Completed","—","#10B981")
        self.stat_closed = self._stat("Closed","—","#6B7280")
        for c in (self.stat_all, self.stat_open, self.stat_prog, self.stat_done, self.stat_closed):
            stats_row.addWidget(c)
        sl.addLayout(stats_row)

        self.search_input = QLineEdit(); self.search_input.setPlaceholderText("🔍  Search…"); self.search_input.setFixedHeight(36)
        self.search_input.textChanged.connect(self._apply_filter); sl.addWidget(self.search_input)

        self.sr_table = QTableWidget(); self.sr_table.setColumnCount(8)
        self.sr_table.setHorizontalHeaderLabels(["Title","Type","Priority","Status","Pipeline","Assigned To","Created","Actions"])
        self.sr_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sr_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.sr_table.setColumnWidth(7, 130)
        self.sr_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sr_table.verticalHeader().setVisible(False); self.sr_table.setAlternatingRowColors(True)
        sl.addWidget(self.sr_table)
        cl.addWidget(self.sr_view)

        # Stats panel
        self.stats_view = StatsPanel(); self.stats_view.setVisible(False)
        cl.addWidget(self.stats_view)

        root.addWidget(self.content_stack)

    def _role_lbl(self, text): l = QLabel(text); l.setStyleSheet("color:#94A3B8;font-size:11px;padding:0 20px;margin-bottom:16px;"); return l

    def _stat(self, label, value, color):
        card = QFrame(); card.setObjectName("stat_card")
        card.setStyleSheet(f"QFrame#stat_card{{background:white;border-radius:10px;border:1px solid #E2E8F0;border-top:4px solid {color};}}")
        lay = QVBoxLayout(card); lay.setContentsMargins(12,10,12,10); lay.setSpacing(3)
        val = QLabel(value); val.setStyleSheet(f"font-size:22px;font-weight:bold;color:{color};")
        lbl = QLabel(label); lbl.setStyleSheet("font-size:11px;color:#64748B;")
        lay.addWidget(val); lay.addWidget(lbl); card._val_label = val; return card

    def _set_filter(self, status: str):
        self._filter = status
        self.sr_view.setVisible(True); self.stats_view.setVisible(False)
        self.nav_stats_btn.setChecked(False)
        for val, btn in self._nav_btns: btn.setChecked(val == status)
        self.page_title.setText("All Service Requests" if status=="all" else status.replace("_"," ").title()+" SRs")
        self._apply_filter()

    def _show_stats(self):
        self.sr_view.setVisible(False); self.stats_view.setVisible(True)
        self.nav_stats_btn.setChecked(True)
        for _, btn in self._nav_btns: btn.setChecked(False)

    def _apply_filter(self):
        search   = self.search_input.text().strip().lower()
        user_map = {u.get("uid",u.get("id","")): u for u in self._users}
        filtered = [
            sr for sr in self._srs
            if (self._filter == "all" or sr.get("status") == self._filter)
            and (not search or search in sr.get("title","").lower() or search in sr.get("description","").lower())
        ]
        self.sr_table.setRowCount(len(filtered))
        for row, sr in enumerate(filtered):
            status = sr.get("status","open")
            ps     = sr.get("pipeline_state")
            if isinstance(ps, dict):
                pipe_txt = f"{ps.get('template_name','?')} ({ps.get('current_step',0)+1}/{ps.get('total_steps',0)})"
            else:
                pipe_txt = "—"
            uid    = sr.get("assigned_to","")
            user   = user_map.get(uid, {})
            uname  = user.get("name","Unassigned")

            cells = [
                truncate(sr.get("title","—"),38), sr.get("type","—").replace("_"," ").title(),
                sr.get("priority","medium").capitalize(), status.replace("_"," ").title(),
                pipe_txt, uname, format_datetime(sr.get("created_at")),
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if col == 3:
                    item.setForeground(QColor(status_color(status))); item.setFont(QFont("",-1,QFont.Weight.Bold))
                self.sr_table.setItem(row, col, item)

            # Actions
            acts = QWidget(); al = QHBoxLayout(acts); al.setContentsMargins(4,2,4,2); al.setSpacing(4)
            open_btn = QPushButton("📂 Open"); open_btn.setFixedHeight(28)
            open_btn.setStyleSheet("QPushButton{background:#3B82F6;color:white;border:none;border-radius:4px;font-size:11px;font-weight:bold;padding:0 6px;}QPushButton:hover{background:#2563EB;}")
            open_btn.clicked.connect(lambda _, s=sr: self._open_detail(s)); al.addWidget(open_btn)
            if status != "closed":
                cb = QPushButton("✅"); cb.setFixedSize(28,28)
                cb.setStyleSheet("QPushButton{background:#10B981;color:white;border:none;border-radius:4px;}QPushButton:hover{background:#059669;}")
                cb.setToolTip("Close SR"); cb.clicked.connect(lambda _, s=sr: self._quick_close(s)); al.addWidget(cb)
            self.sr_table.setCellWidget(row, 7, acts); self.sr_table.setRowHeight(row, 44)

    def _refresh(self):
        w = LoadDataWorker()
        w.done.connect(self._on_data)
        w.error.connect(self._on_error)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w); w.start()

    @pyqtSlot(list, list, list)
    def _on_data(self, srs, users, templates):
        self._srs = srs; self._users = users; self._templates = templates
        self.sync_lbl.setText("● Offline Mode"); self.sync_lbl.setStyleSheet("color:#10B981;font-size:11px;padding:0 20px;")
        self.stat_all._val_label.setText(str(len(srs)))
        self.stat_open._val_label.setText(str(sum(1 for s in srs if s.get("status")=="open")))
        self.stat_prog._val_label.setText(str(sum(1 for s in srs if s.get("status")=="in_progress")))
        self.stat_done._val_label.setText(str(sum(1 for s in srs if s.get("status")=="completed")))
        self.stat_closed._val_label.setText(str(sum(1 for s in srs if s.get("status")=="closed")))
        self._apply_filter()
        self.stats_view.populate_user_filter(users)

    def _on_error(self, msg):
        self.sync_lbl.setText("⚠ Sync Error"); self.sync_lbl.setStyleSheet("color:#EF4444;font-size:11px;padding:0 20px;")

    def _manual_sync(self):
        self.sync_lbl.setText("↻ Checking…")
        w = SyncNowWorker()
        w.done.connect(self._on_manual_sync_done)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w); w.start()

    def _on_manual_sync_done(self, result: dict):
        if result.get("ok"):
            self.sync_lbl.setText("● Saved Locally")
            self._refresh()
        else:
            self.sync_lbl.setText("● Saved Locally")

    def _open_create(self):
        from ui.create_sr_dialog import CreateSRDialog as NewCreateSRDialog
        dlg = NewCreateSRDialog(parent=self, users=self._users)
        dlg.sr_created.connect(lambda doc: self._refresh())
        dlg.exec()

    def _open_detail(self, sr):
        dlg = SRDetailDialog(sr, self._users, self); dlg.sr_updated.connect(self._refresh); dlg.exec()

    def _quick_close(self, sr):
        if QMessageBox.question(self, "Close SR", f"Close '{sr.get('title','')}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            w = UpdateSRWorker(sr["id"], {"status":"closed","updated_at":utc_now_iso()})
            w.done.connect(self._refresh); w.error.connect(lambda msg: QMessageBox.critical(self,"Error",msg))
            self._workers.append(w); w.start()

    def _logout(self):
        self.stop_polling(); storage.logout(); self.logout_requested.emit()
