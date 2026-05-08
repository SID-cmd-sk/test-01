# ui/technical_dashboard.py
"""
Technical Dashboard:
- View own SRs (assigned or self-created)
- Create self-assigned SR
- Update status + advance pipeline steps
- Skip step with mandatory reason
- Request help via email
- Own statistics tab
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QLineEdit, QComboBox, QDialog, QFormLayout, QMessageBox,
    QTextEdit, QGroupBox, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import QColor, QFont

from db import storage
from utils.auth import session
from utils.helpers import (
    format_datetime, status_color, utc_now_iso,
    validate_required, truncate
)
from ui.stats_panel import StatsPanel
from services.pipeline_service import pipeline_service


# ── Workers ───────────────────────────────────────────────────────────────────

class LoadMyDataWorker(QThread):
    done  = pyqtSignal(list, list)
    error = pyqtSignal(str)

    def run(self):
        try:
            all_srs = storage.get_collection("service_requests")
            uid     = session.uid
            my_srs  = [s for s in all_srs
                       if s.get("assigned_to")==uid or s.get("created_by")==uid]
            users   = storage.get_collection("users")
            self.done.emit(my_srs, users)
        except Exception as e:
            self.error.emit(str(e))


class CreateSRWorker(QThread):
    done  = pyqtSignal()
    error = pyqtSignal(str)
    def __init__(self, data): super().__init__(); self.data = data
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
    def __init__(self, sr_id, updates): super().__init__(); self.sr_id=sr_id; self.updates=updates
    def run(self):
        try:
            storage.update_document("service_requests", self.sr_id, self.updates)
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))


class SendHelpWorker(QThread):
    done  = pyqtSignal()
    error = pyqtSignal(str)
    def __init__(self, recipients): super().__init__(); self.recipients = recipients
    def run(self):
        try:
            from services.email_service import send_help_request
            send_help_request(session.name, session.email or "", self.recipients)
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))


# ── Create SR Dialog ──────────────────────────────────────────────────────────

class TechCreateSRDialog(QDialog):
    sr_created = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Service Request")
        self.setFixedSize(460, 370)
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setSpacing(12); lay.setContentsMargins(24,24,24,24)
        ttl = QLabel("📋  Create Service Request"); ttl.setStyleSheet("font-size:16px;font-weight:bold;color:#0F172A;"); lay.addWidget(ttl)
        info = QLabel("Self-created SR — assigned to you. Managers can monitor progress.")
        info.setObjectName("info_label"); info.setWordWrap(True); lay.addWidget(info)

        form = QFormLayout(); form.setSpacing(10)
        self.title_input = QLineEdit(); self.title_input.setPlaceholderText("Short title"); self.title_input.setFixedHeight(36)
        self.desc_input  = QTextEdit(); self.desc_input.setPlaceholderText("Detailed description…"); self.desc_input.setFixedHeight(100)
        self.priority    = QComboBox(); self.priority.addItems(["low","medium","high"]); self.priority.setCurrentText("medium"); self.priority.setFixedHeight(36)
        form.addRow("Title *",       self.title_input)
        form.addRow("Description *", self.desc_input)
        form.addRow("Priority",      self.priority)
        lay.addLayout(form)

        self.err_lbl = QLabel(""); self.err_lbl.setObjectName("error_label"); self.err_lbl.setVisible(False); lay.addWidget(self.err_lbl)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancel"); cancel.setObjectName("btn_secondary"); cancel.clicked.connect(self.reject)
        self.sub_btn = QPushButton("Create SR"); self.sub_btn.setObjectName("btn_primary"); self.sub_btn.clicked.connect(self._submit)
        btn_row.addWidget(cancel); btn_row.addWidget(self.sub_btn); lay.addLayout(btn_row)

    def _submit(self):
        title = self.title_input.text().strip(); desc = self.desc_input.toPlainText().strip()
        ok, msg = validate_required(title,"Title")
        if not ok: return self._err(msg)
        ok, msg = validate_required(desc,"Description")
        if not ok: return self._err(msg)

        now = utc_now_iso(); uid = session.uid
        data = {
            "title": title, "description": desc,
            "created_by": uid, "assigned_to": uid,
            "type": "self_created", "status": "open",
            "priority": self.priority.currentText(),
            "created_at": now, "updated_at": now,
        }
        self.sub_btn.setEnabled(False); self.sub_btn.setText("Creating…")
        self._worker = CreateSRWorker(data)
        self._worker.done.connect(lambda: (self.sr_created.emit(), self.accept()))
        self._worker.error.connect(lambda e: (self._err(e), self.sub_btn.setEnabled(True), self.sub_btn.setText("Create SR")))
        self._worker.start()

    def _err(self, msg): self.err_lbl.setText(f"⚠ {msg}"); self.err_lbl.setVisible(True)


# ── SR Update + Pipeline Dialog ───────────────────────────────────────────────

class TechUpdateDialog(QDialog):
    updated = pyqtSignal()

    def __init__(self, sr: dict, parent=None):
        super().__init__(parent)
        self.sr = sr
        self.setWindowTitle(f"Update — {sr.get('title','')}")
        self.setMinimumSize(500, 500)
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setSpacing(12); lay.setContentsMargins(24,24,24,24)

        ttl = QLabel(self.sr.get("title","—")); ttl.setStyleSheet("font-size:15px;font-weight:bold;color:#0F172A;"); ttl.setWordWrap(True); lay.addWidget(ttl)

        current_status = self.sr.get("status","open")
        s_lbl = QLabel(f"Status: {current_status.replace('_',' ').upper()}")
        s_lbl.setStyleSheet(f"color:white;background:{status_color(current_status)};border-radius:4px;padding:3px 12px;font-size:12px;font-weight:bold;")
        lay.addWidget(s_lbl)

        desc_grp = QGroupBox("Description"); dl = QVBoxLayout(desc_grp)
        d = QLabel(self.sr.get("description","—")); d.setWordWrap(True); d.setStyleSheet("font-size:12px;color:#374151;")
        dl.addWidget(d); lay.addWidget(desc_grp)

        # Pipeline progress
        ps = self.sr.get("pipeline_state")
        self._pipeline_state = ps
        if isinstance(ps, dict) and ps.get("steps_state"):
            pipe_grp = QGroupBox(f"Pipeline: {ps.get('template_name','?')}")
            pl = QVBoxLayout(pipe_grp); current_idx = ps.get("current_step",0)

            for step in ps.get("steps_state",[]):
                si    = step.get("index",0)
                sstat = step.get("status","pending")
                if sstat == "done":   icon, col = "✅", "#10B981"
                elif sstat == "skipped": icon, col = "⏭", "#F59E0B"
                elif si == current_idx: icon, col = "▶", "#3B82F6"
                else:                icon, col = "○", "#94A3B8"
                row_lbl = QLabel(f"{icon}  {step.get('name','?')}  [{step.get('approver_role','?')}]"
                                 + (f"  — {step.get('skip_reason','')}" if sstat=="skipped" else ""))
                row_lbl.setStyleSheet(f"color:{col};font-size:12px;")
                pl.addWidget(row_lbl)

            # Current step actions (only if it's this user's role)
            if current_idx < len(ps.get("steps_state",[])):
                cur_step = ps["steps_state"][current_idx]
                approver = cur_step.get("approver_role","technical")
                can_act  = (session.role == approver or session.can("skip_pipeline_steps"))

                if can_act and cur_step.get("status") == "pending":
                    step_btns = QHBoxLayout()
                    adv_btn = QPushButton(f"✅ Complete: {cur_step.get('name','Step')}")
                    adv_btn.setObjectName("btn_success")
                    adv_btn.clicked.connect(self._advance_step)
                    step_btns.addWidget(adv_btn)

                    if cur_step.get("skippable", True) and session.can("skip_pipeline_steps"):
                        skip_btn = QPushButton("⏭ Skip Step")
                        skip_btn.setObjectName("btn_warning")
                        skip_btn.clicked.connect(self._skip_step)
                        step_btns.addWidget(skip_btn)

                    step_btns.addStretch()
                    step_btns_w = QWidget(); step_btns_w.setLayout(step_btns)
                    pl.addWidget(step_btns_w)

            lay.addWidget(pipe_grp)

        # Status update (only if no pipeline, or pipeline complete)
        pipeline_complete = True
        if isinstance(ps, dict):
            pipeline_complete = pipeline_service.is_pipeline_complete(ps)

        if not isinstance(ps, dict) or pipeline_complete:
            upd_grp = QGroupBox("Update Status"); upd_form = QFormLayout(upd_grp)
            self.status_combo = QComboBox(); self.status_combo.setFixedHeight(34)
            allowed = {"open":["in_progress"],"in_progress":["in_progress","completed"],
                       "completed":["completed"],"closed":["closed"]}
            for s in allowed.get(current_status,["in_progress","completed"]):
                self.status_combo.addItem(s.replace("_"," ").title(), s)

            self.notes_input = QTextEdit(); self.notes_input.setPlaceholderText("Progress notes or resolution details…"); self.notes_input.setFixedHeight(70)
            upd_form.addRow("New Status:", self.status_combo)
            upd_form.addRow("Notes:",      self.notes_input)
            lay.addWidget(upd_grp)
        else:
            self.status_combo = None; self.notes_input = None

        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancel"); cancel.setObjectName("btn_secondary"); cancel.clicked.connect(self.reject)
        self.save_btn = QPushButton("Save Update"); self.save_btn.setObjectName("btn_primary"); self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel); btn_row.addWidget(self.save_btn); lay.addLayout(btn_row)

    def _advance_step(self):
        sr_id  = self.sr.get("id","")
        ps     = self._pipeline_state
        notes  = self.notes_input.toPlainText().strip() if self.notes_input else ""
        try:
            updated_ps = pipeline_service.advance_step(sr_id, ps, notes, session.uid)
            self._pipeline_state = updated_ps
            # Check if pipeline done → auto set completed
            if pipeline_service.is_pipeline_complete(updated_ps):
                storage.update_document("service_requests", sr_id,
                    {"status":"completed","completed_at":utc_now_iso(),"updated_at":utc_now_iso()})
                QMessageBox.information(self,"Pipeline Complete","All steps done. SR marked Completed.")
            else:
                QMessageBox.information(self,"Step Advanced","Step marked complete. Next step is now active.")
            self.updated.emit(); self.accept()
        except Exception as e:
            QMessageBox.critical(self,"Error",str(e))

    def _skip_step(self):
        reason, ok = QInputDialog.getText(self, "Skip Step",
            "Reason for skipping this step (required):")
        if not ok or not reason.strip():
            QMessageBox.warning(self,"Required","A reason is required to skip a step."); return
        sr_id = self.sr.get("id","")
        ps    = self._pipeline_state
        try:
            updated_ps = pipeline_service.skip_step(sr_id, ps, reason.strip(), session.uid)
            self._pipeline_state = updated_ps
            from services.audit_service import log_action
            log_action("step_skipped", reason.strip(), sr_id)
            QMessageBox.information(self,"Skipped",f"Step skipped: {reason}")
            self.updated.emit(); self.accept()
        except Exception as e:
            QMessageBox.critical(self,"Error",str(e))

    def _save(self):
        if not self.status_combo:
            self.accept(); return
        new_status = self.status_combo.currentData()
        notes      = self.notes_input.toPlainText().strip() if self.notes_input else ""
        updates    = {"status":new_status,"notes":notes,"updated_at":utc_now_iso()}
        if new_status == "completed": updates["completed_at"] = utc_now_iso()
        self.save_btn.setEnabled(False); self.save_btn.setText("Saving…")
        self._worker = UpdateSRWorker(self.sr["id"], updates)
        self._worker.done.connect(lambda: (self.updated.emit(), self.accept()))
        self._worker.error.connect(lambda msg: (
            QMessageBox.critical(self,"Error",msg),
            self.save_btn.setEnabled(True), self.save_btn.setText("Save Update")
        ))
        self._worker.start()


# ── Technical Dashboard ───────────────────────────────────────────────────────

class TechnicalDashboard(QWidget):
    logout_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._srs:   list = []
        self._users: list = []
        self._filter = "all"
        self._poll_timer = QTimer(); self._poll_timer.setInterval(3000)
        self._poll_timer.timeout.connect(self._refresh)
        self._workers: list = []
        self._build_ui()

    def start_polling(self): self._refresh(); self._poll_timer.start()
    def stop_polling(self):  self._poll_timer.stop()

    def _build_ui(self):
        root = QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        sidebar = QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(230)
        sb = QVBoxLayout(sidebar); sb.setContentsMargins(0,20,0,20); sb.setSpacing(4)
        brand = QLabel("🛠  SR Manager"); brand.setStyleSheet("color:white;font-size:15px;font-weight:bold;padding:0 20px;margin-bottom:8px;"); sb.addWidget(brand)
        rl = QLabel(f"Technical  •  {session.name}"); rl.setStyleSheet("color:#94A3B8;font-size:11px;padding:0 20px;margin-bottom:16px;"); sb.addWidget(rl)

        for val, label in [("all","📋  My SRs"),("open","🔵  Open"),("in_progress","🟡  In Progress"),("completed","🟢  Completed")]:
            btn = QPushButton(label); btn.setObjectName("sidebar_nav"); btn.setCheckable(True)
            btn.clicked.connect(lambda _, v=val: self._set_filter(v)); sb.addWidget(btn)

        self.nav_stats_btn = QPushButton("📊  My Stats"); self.nav_stats_btn.setObjectName("sidebar_nav"); self.nav_stats_btn.setCheckable(True)
        self.nav_stats_btn.clicked.connect(self._show_stats); sb.addWidget(self.nav_stats_btn)

        sb.addStretch()
        self.sync_lbl = QLabel("● Live"); self.sync_lbl.setStyleSheet("color:#10B981;font-size:11px;padding:0 20px;"); sb.addWidget(self.sync_lbl)
        logout_btn = QPushButton("🚪  Log Out"); logout_btn.setStyleSheet("QPushButton{background:transparent;color:#94A3B8;border:none;text-align:left;padding:10px 20px;}QPushButton:hover{color:#EF4444;}")
        logout_btn.clicked.connect(self._logout); sb.addWidget(logout_btn)
        root.addWidget(sidebar)

        self.content = QWidget(); self.content.setStyleSheet("background:#F1F5F9;")
        cl = QVBoxLayout(self.content); cl.setContentsMargins(24,24,24,24); cl.setSpacing(16)

        # SR View
        self.sr_view = QWidget()
        sl = QVBoxLayout(self.sr_view); sl.setContentsMargins(0,0,0,0); sl.setSpacing(16)

        hdr = QHBoxLayout()
        self.page_title = QLabel("My Service Requests"); self.page_title.setObjectName("section_title"); hdr.addWidget(self.page_title); hdr.addStretch()
        help_btn   = QPushButton("📧 Request Help"); help_btn.setObjectName("btn_secondary"); help_btn.clicked.connect(self._request_help)
        create_btn = QPushButton("+ New SR"); create_btn.setObjectName("btn_primary"); create_btn.clicked.connect(self._open_create)
        hdr.addWidget(help_btn); hdr.addWidget(create_btn); sl.addLayout(hdr)

        stats_row = QHBoxLayout()
        self.stat_total = self._stat("My SRs","—","#3B82F6"); self.stat_open = self._stat("Open","—","#F59E0B")
        self.stat_prog  = self._stat("In Progress","—","#8B5CF6"); self.stat_done = self._stat("Completed","—","#10B981")
        for c in (self.stat_total, self.stat_open, self.stat_prog, self.stat_done): stats_row.addWidget(c)
        sl.addLayout(stats_row)

        self.sr_table = QTableWidget(); self.sr_table.setColumnCount(7)
        self.sr_table.setHorizontalHeaderLabels(["Title","Type","Priority","Status","Pipeline","Updated","Actions"])
        self.sr_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sr_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.sr_table.setColumnWidth(6, 180)
        self.sr_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sr_table.verticalHeader().setVisible(False); self.sr_table.setAlternatingRowColors(True)
        sl.addWidget(self.sr_table); cl.addWidget(self.sr_view)

        self.stats_view = StatsPanel(); self.stats_view.setVisible(False); cl.addWidget(self.stats_view)
        root.addWidget(self.content)

    def _stat(self, label, value, color):
        card = QFrame(); card.setObjectName("stat_card")
        card.setStyleSheet(f"QFrame#stat_card{{background:white;border-radius:10px;border:1px solid #E2E8F0;border-top:4px solid {color};}}")
        lay = QVBoxLayout(card); lay.setContentsMargins(12,10,12,10); lay.setSpacing(3)
        val = QLabel(value); val.setStyleSheet(f"font-size:22px;font-weight:bold;color:{color};")
        lbl = QLabel(label); lbl.setStyleSheet("font-size:11px;color:#64748B;")
        lay.addWidget(val); lay.addWidget(lbl); card._val_label = val; return card

    def _set_filter(self, status: str):
        self._filter = status
        self.sr_view.setVisible(True); self.stats_view.setVisible(False); self.nav_stats_btn.setChecked(False)
        self.page_title.setText("My Service Requests" if status=="all" else status.replace("_"," ").title()+" SRs")
        self._apply_filter()

    def _show_stats(self):
        self.sr_view.setVisible(False); self.stats_view.setVisible(True); self.nav_stats_btn.setChecked(True)

    def _apply_filter(self):
        filtered = [s for s in self._srs if self._filter=="all" or s.get("status")==self._filter]
        self.sr_table.setRowCount(len(filtered))
        for row, sr in enumerate(filtered):
            status = sr.get("status","open")
            ps     = sr.get("pipeline_state")
            if isinstance(ps, dict):
                pipe_txt = f"{ps.get('template_name','?')} ({ps.get('current_step',0)+1}/{ps.get('total_steps',0)})"
            else:
                pipe_txt = "—"
            cells = [
                truncate(sr.get("title","—"),38),
                "🖊 Self" if sr.get("type")=="self_created" else "📤 Assigned",
                sr.get("priority","medium").capitalize(),
                status.replace("_"," ").title(),
                pipe_txt,
                format_datetime(sr.get("updated_at")),
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if col == 3:
                    item.setForeground(QColor(status_color(status))); item.setFont(QFont("",-1,QFont.Weight.Bold))
                self.sr_table.setItem(row, col, item)

            acts = QWidget(); al = QHBoxLayout(acts); al.setContentsMargins(4,2,4,2); al.setSpacing(4)
            if status not in ("completed","closed"):
                upd = QPushButton("✏ Update"); upd.setFixedHeight(28)
                upd.setStyleSheet("QPushButton{background:#8B5CF6;color:white;border:none;border-radius:4px;font-size:11px;font-weight:bold;padding:0 6px;}QPushButton:hover{background:#7C3AED;}")
                upd.clicked.connect(lambda _, s=sr: self._open_update(s)); al.addWidget(upd)
                if status == "open":
                    sb = QPushButton("▶"); sb.setFixedSize(28,28)
                    sb.setStyleSheet("QPushButton{background:#F59E0B;color:white;border:none;border-radius:4px;}QPushButton:hover{background:#D97706;}")
                    sb.setToolTip("Start"); sb.clicked.connect(lambda _, s=sr: self._quick_start(s)); al.addWidget(sb)
                if status == "in_progress":
                    cb = QPushButton("✅"); cb.setFixedSize(28,28)
                    cb.setStyleSheet("QPushButton{background:#10B981;color:white;border:none;border-radius:4px;}QPushButton:hover{background:#059669;}")
                    cb.setToolTip("Complete"); cb.clicked.connect(lambda _, s=sr: self._quick_complete(s)); al.addWidget(cb)
            else:
                dl = QLabel("✓ Done" if status=="completed" else "Closed")
                dl.setStyleSheet(f"color:{status_color(status)};font-size:11px;font-weight:bold;padding:0 6px;"); al.addWidget(dl)
            self.sr_table.setCellWidget(row, 6, acts); self.sr_table.setRowHeight(row, 44)

    def _refresh(self):
        w = LoadMyDataWorker()
        w.done.connect(self._on_data); w.error.connect(self._on_error)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w); w.start()

    @pyqtSlot(list, list)
    def _on_data(self, my_srs, users):
        self._srs = my_srs; self._users = users
        self.sync_lbl.setText("● Live"); self.sync_lbl.setStyleSheet("color:#10B981;font-size:11px;padding:0 20px;")
        self.stat_total._val_label.setText(str(len(my_srs)))
        self.stat_open._val_label.setText(str(sum(1 for s in my_srs if s.get("status")=="open")))
        self.stat_prog._val_label.setText(str(sum(1 for s in my_srs if s.get("status")=="in_progress")))
        self.stat_done._val_label.setText(str(sum(1 for s in my_srs if s.get("status")=="completed")))
        self._apply_filter()

    def _on_error(self, msg):
        self.sync_lbl.setText("⚠ Sync Error"); self.sync_lbl.setStyleSheet("color:#EF4444;font-size:11px;padding:0 20px;")

    def _open_create(self):
        from ui.create_sr_dialog import CreateSRDialog
        dlg = CreateSRDialog(parent=self, users=[])
        dlg.sr_created.connect(lambda doc: self._refresh())
        dlg.exec()
    def _open_update(self, sr): dlg = TechUpdateDialog(sr, self); dlg.updated.connect(self._refresh); dlg.exec()

    def _quick_start(self, sr):
        w = UpdateSRWorker(sr["id"], {"status":"in_progress","updated_at":utc_now_iso()})
        w.done.connect(self._refresh); w.error.connect(lambda m: QMessageBox.critical(self,"Error",m))
        self._workers.append(w); w.start()

    def _quick_complete(self, sr):
        if QMessageBox.question(self,"Complete",f"Mark '{sr.get('title','')}' as completed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            w = UpdateSRWorker(sr["id"],{"status":"completed","updated_at":utc_now_iso(),"completed_at":utc_now_iso()})
            w.done.connect(self._refresh); w.error.connect(lambda m: QMessageBox.critical(self,"Error",m))
            self._workers.append(w); w.start()

    def _request_help(self):
        recipients = [u.get("email") for u in self._users
                      if u.get("role") in ("admin","manager") and u.get("email")]
        if not recipients: QMessageBox.warning(self,"No Recipients","No admin/manager emails found."); return
        w = SendHelpWorker(recipients)
        w.done.connect(lambda: QMessageBox.information(self,"Sent","Help request emailed to management."))
        w.error.connect(lambda m: QMessageBox.critical(self,"Email Failed",m))
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w); w.start()

    def _logout(self):
        self.stop_polling(); storage.logout(); self.logout_requested.emit()
