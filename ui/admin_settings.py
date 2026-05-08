# ui/admin_settings.py
"""
Admin Settings Panel — 5 sections:
  1. Branding (app name, company, primary color, label overrides)
  2. WhatsApp (QR mode + Meta Cloud API mode)
  3. Email / SMTP
  4. Notifications (per-event toggles + templates)
  5. Danger Zone
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QCheckBox,
    QMessageBox, QFrame, QScrollArea, QGroupBox, QComboBox,
    QColorDialog, QTabWidget, QSizePolicy, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor

from services.config_service import global_config
from utils.helpers import validate_time, build_stylesheet


# ── Worker ────────────────────────────────────────────────────────────────────

class SaveSettingsWorker(QThread):
    done  = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, data: dict):
        super().__init__()
        self.data = data

    def run(self):
        try:
            global_config.save(self.data)
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))


# ── Color picker button ───────────────────────────────────────────────────────

class ColorButton(QPushButton):
    color_changed = pyqtSignal(str)

    def __init__(self, color: str = "#3B82F6", parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(80, 32)
        self._apply()
        self.clicked.connect(self._pick)

    def _apply(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background: {self._color}; border-radius: 6px;
                border: 2px solid #CBD5E1; color: white; font-weight: bold;
            }}
        """)
        self.setText(self._color)

    def _pick(self):
        col = QColorDialog.getColor(QColor(self._color), self, "Pick Primary Color")
        if col.isValid():
            self._color = col.name()
            self._apply()
            self.color_changed.emit(self._color)

    def get_color(self) -> str:
        return self._color

    def set_color(self, color: str):
        self._color = color
        self._apply()


# ── Admin Settings Panel ──────────────────────────────────────────────────────

class AdminSettingsPanel(QWidget):
    stylesheet_changed = pyqtSignal(str)   # emits new QSS string

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._wa_widget = None
        self._build_ui()
        self._load_values()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(4, 4, 4, 16)
        lay.setSpacing(0)

        # Title
        ttl = QLabel("⚙️  Global Settings")
        ttl.setObjectName("section_title")
        ttl.setContentsMargins(0, 0, 0, 12)
        lay.addWidget(ttl)

        # Tabs
        tabs = QTabWidget()

        tabs.addTab(self._build_branding_tab(),       "🎨 Branding")
        tabs.addTab(self._build_whatsapp_tab(),        "📱 WhatsApp")
        tabs.addTab(self._build_email_tab(),           "📧 Email")
        tabs.addTab(self._build_notifications_tab(),   "🔔 Notifications")
        tabs.addTab(self._build_cloud_tab(),           "☁ Cloud Sync")
        tabs.addTab(self._build_danger_tab(),          "☠ Danger Zone")

        lay.addWidget(tabs)

        # Global save button
        save_row = QHBoxLayout()
        save_row.addStretch()
        self.save_btn = QPushButton("💾  Save All Settings")
        self.save_btn.setObjectName("btn_primary")
        self.save_btn.setFixedHeight(40)
        self.save_btn.setMinimumWidth(200)
        self.save_btn.clicked.connect(self._save)
        save_row.addWidget(self.save_btn)
        lay.addLayout(save_row)

        scroll.setWidget(container)
        outer.addWidget(scroll)

    # ── Branding tab ──────────────────────────────────────────────────────────

    def _build_branding_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(16)
        lay.setContentsMargins(16, 16, 16, 16)

        # General
        gen = QGroupBox("App Identity")
        gf  = QFormLayout(gen); gf.setSpacing(10)

        self.app_name     = QLineEdit(); self.app_name.setPlaceholderText("SR Manager"); self.app_name.setFixedHeight(36)
        self.company_name = QLineEdit(); self.company_name.setPlaceholderText("Your Company"); self.company_name.setFixedHeight(36)

        gf.addRow("App Name:",     self.app_name)
        gf.addRow("Company Name:", self.company_name)

        # Color picker
        color_row = QHBoxLayout()
        self.color_btn = ColorButton()
        self.color_btn.color_changed.connect(self._preview_color)
        color_row.addWidget(self.color_btn)
        color_row.addWidget(QLabel("   Changes sidebar, buttons, and active elements live."))
        color_row.addStretch()
        gf.addRow("Primary Color:", color_row)

        lay.addWidget(gen)

        # Label overrides
        lbl_grp = QGroupBox("UI Label Overrides  (leave blank to use defaults)")
        lf = QFormLayout(lbl_grp); lf.setSpacing(10)

        self.lbl_sr          = QLineEdit(); self.lbl_sr.setPlaceholderText("Service Request"); self.lbl_sr.setFixedHeight(34)
        self.lbl_open        = QLineEdit(); self.lbl_open.setPlaceholderText("Open"); self.lbl_open.setFixedHeight(34)
        self.lbl_in_progress = QLineEdit(); self.lbl_in_progress.setPlaceholderText("In Progress"); self.lbl_in_progress.setFixedHeight(34)
        self.lbl_completed   = QLineEdit(); self.lbl_completed.setPlaceholderText("Completed"); self.lbl_completed.setFixedHeight(34)
        self.lbl_closed      = QLineEdit(); self.lbl_closed.setPlaceholderText("Closed"); self.lbl_closed.setFixedHeight(34)

        lf.addRow("'Service Request' →", self.lbl_sr)
        lf.addRow("'Open' →",            self.lbl_open)
        lf.addRow("'In Progress' →",     self.lbl_in_progress)
        lf.addRow("'Completed' →",       self.lbl_completed)
        lf.addRow("'Closed' →",          self.lbl_closed)

        lay.addWidget(lbl_grp)
        lay.addStretch()
        return w

    # ── WhatsApp tab ──────────────────────────────────────────────────────────

    def _build_whatsapp_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(16)
        lay.setContentsMargins(16, 16, 16, 16)

        # Mode selector
        mode_grp = QGroupBox("WhatsApp Mode")
        mf = QFormLayout(mode_grp); mf.setSpacing(10)

        self.wa_mode = QComboBox()
        self.wa_mode.addItem("📱 QR Code (WhatsApp Web — scan once)", "qr")
        self.wa_mode.addItem("☁ Meta Cloud API (Business number)", "meta")
        self.wa_mode.setFixedHeight(36)
        self.wa_mode.currentIndexChanged.connect(self._on_wa_mode_change)
        mf.addRow("Mode:", self.wa_mode)
        lay.addWidget(mode_grp)

        # QR section
        self.qr_grp = QGroupBox("WhatsApp Web — QR Session")
        qf = QVBoxLayout(self.qr_grp)

        from ui.whatsapp_qr_widget import WhatsAppQRWidget
        self._wa_widget = WhatsAppQRWidget()
        self._wa_widget.setMinimumHeight(460)
        qf.addWidget(self._wa_widget)

        test_row = QHBoxLayout()
        test_btn = QPushButton("📤 Send Test Message")
        test_btn.setObjectName("btn_secondary")
        test_btn.clicked.connect(self._test_wa_qr)
        test_row.addWidget(test_btn); test_row.addStretch()
        qf.addLayout(test_row)
        lay.addWidget(self.qr_grp)

        # Meta section
        self.meta_grp = QGroupBox("Meta Cloud API")
        metaf = QFormLayout(self.meta_grp); metaf.setSpacing(10)

        self.meta_phone_id    = QLineEdit(); self.meta_phone_id.setPlaceholderText("Phone Number ID"); self.meta_phone_id.setFixedHeight(36)
        self.meta_token       = QLineEdit(); self.meta_token.setPlaceholderText("Permanent Access Token"); self.meta_token.setFixedHeight(36)
        self.meta_token.setEchoMode(QLineEdit.EchoMode.Password)

        metaf.addRow("Phone Number ID:", self.meta_phone_id)
        metaf.addRow("Access Token:",    self.meta_token)

        meta_note = QLabel(
            "ℹ  Get these from Meta for Developers → WhatsApp → API Setup.\n"
            "Free tier: 1,000 conversations/month."
        )
        meta_note.setObjectName("info_label"); meta_note.setWordWrap(True)
        metaf.addRow("", meta_note)

        test_meta_btn = QPushButton("📤 Send Test (Meta)")
        test_meta_btn.setObjectName("btn_secondary")
        test_meta_btn.clicked.connect(self._test_wa_meta)
        metaf.addRow("", test_meta_btn)

        lay.addWidget(self.meta_grp)
        self.meta_grp.setVisible(False)

        # Report schedule
        sched_grp = QGroupBox("Daily Report Schedule")
        sf = QFormLayout(sched_grp); sf.setSpacing(10)

        self.report_time   = QLineEdit(); self.report_time.setPlaceholderText("HH:MM (24h)"); self.report_time.setFixedHeight(36)
        self.wa_template   = QTextEdit(); self.wa_template.setPlaceholderText("{company_name} Daily SR Report\n{report}"); self.wa_template.setFixedHeight(90)
        self.wa_number     = QLineEdit(); self.wa_number.setPlaceholderText("Default number (Meta mode only)"); self.wa_number.setFixedHeight(36)

        sf.addRow("Report Time:", self.report_time)
        sf.addRow("Template:",    self.wa_template)
        sf.addRow("Default No.:", self.wa_number)
        lay.addWidget(sched_grp)

        lay.addStretch()
        return w

    # ── Email tab ─────────────────────────────────────────────────────────────

    def _build_email_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(16)
        lay.setContentsMargins(16, 16, 16, 16)

        smtp_grp = QGroupBox("SMTP Configuration (Gmail)")
        sf = QFormLayout(smtp_grp); sf.setSpacing(10)

        self.smtp_email    = QLineEdit(); self.smtp_email.setPlaceholderText("sender@gmail.com"); self.smtp_email.setFixedHeight(36)
        self.smtp_password = QLineEdit(); self.smtp_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.smtp_password.setPlaceholderText("Gmail App Password (16 chars)"); self.smtp_password.setFixedHeight(36)
        self.email_template = QTextEdit()
        self.email_template.setPlaceholderText("{company_name}\n\n{body}")
        self.email_template.setFixedHeight(100)

        sf.addRow("SMTP Email:",     self.smtp_email)
        sf.addRow("SMTP Password:",  self.smtp_password)
        sf.addRow("Email Template:", self.email_template)

        note = QLabel(
            "ℹ  For Gmail, use an App Password:\n"
            "Google Account → Security → 2-Step Verification → App passwords."
        )
        note.setObjectName("info_label"); note.setWordWrap(True)
        sf.addRow("", note)

        test_btn = QPushButton("📧 Send Test Email to Myself")
        test_btn.setObjectName("btn_secondary")
        test_btn.clicked.connect(self._test_email)
        sf.addRow("", test_btn)

        lay.addWidget(smtp_grp)
        lay.addStretch()
        return w

    # ── Notifications tab ─────────────────────────────────────────────────────

    def _build_notifications_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(16)
        lay.setContentsMargins(16, 16, 16, 16)

        ev_grp = QGroupBox("Event Triggers  (send WhatsApp notification when…)")
        ef = QVBoxLayout(ev_grp); ef.setSpacing(8)

        self.notify_sr_created   = QCheckBox("New SR is created")
        self.notify_sr_assigned  = QCheckBox("SR is assigned to a user")
        self.notify_step_done    = QCheckBox("Pipeline step is completed")
        self.notify_sr_closed    = QCheckBox("SR is closed")
        self.notify_daily_report = QCheckBox("Daily report time (sends summary)")

        for chk in (self.notify_sr_created, self.notify_sr_assigned,
                    self.notify_step_done, self.notify_sr_closed,
                    self.notify_daily_report):
            ef.addWidget(chk)

        lay.addWidget(ev_grp)

        audit_grp = QGroupBox("Audit Log")
        af = QVBoxLayout(audit_grp)
        self.audit_enabled = QCheckBox("Enable audit log (records every action locally)")
        af.addWidget(self.audit_enabled)
        lay.addWidget(audit_grp)

        lay.addStretch()
        return w

    # ── Danger Zone tab ───────────────────────────────────────────────────────

    def _build_cloud_tab(self) -> QWidget:
        """Cloud Sync tab — delegates to CloudSyncSettingsPanel."""
        from ui.cloud_sync_settings import CloudSyncSettingsPanel
        self._cloud_settings = CloudSyncSettingsPanel()
        return self._cloud_settings

    def _build_danger_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(16)
        lay.setContentsMargins(16, 16, 16, 16)

        warn = QLabel("⚠  These actions are irreversible. Proceed with extreme caution.")
        warn.setStyleSheet("background: #FEF2F2; border: 1px solid #EF4444; border-radius: 8px;"
                           "padding: 12px; color: #991B1B; font-weight: bold;")
        warn.setWordWrap(True)
        lay.addWidget(warn)

        # Export
        exp_grp = QGroupBox("Data Export")
        ef = QVBoxLayout(exp_grp); ef.setSpacing(8)
        exp_csv_btn = QPushButton("📥 Export All SRs to CSV")
        exp_csv_btn.setObjectName("btn_secondary")
        exp_csv_btn.clicked.connect(self._export_csv)
        ef.addWidget(exp_csv_btn)
        lay.addWidget(exp_grp)

        # Reset settings
        reset_grp = QGroupBox("Reset")
        rf = QVBoxLayout(reset_grp); rf.setSpacing(8)

        reset_settings_btn = QPushButton("🔄 Reset Settings to Default")
        reset_settings_btn.setObjectName("btn_warning")
        reset_settings_btn.clicked.connect(self._reset_settings)
        rf.addWidget(reset_settings_btn)
        lay.addWidget(reset_grp)

        # Wipe SRs
        wipe_grp = QGroupBox("Danger")
        wf = QVBoxLayout(wipe_grp); wf.setSpacing(8)

        wipe_sr_btn = QPushButton("💣 Wipe ALL Service Requests")
        wipe_sr_btn.setObjectName("btn_danger")
        wipe_sr_btn.clicked.connect(self._wipe_srs)
        wf.addWidget(wipe_sr_btn)

        lay.addWidget(wipe_grp)
        lay.addStretch()
        return w

    # ── Load / Save ───────────────────────────────────────────────────────────

    def _load_values(self):
        cfg = global_config.get()

        self.app_name.setText(cfg.get("app_name", ""))
        self.company_name.setText(cfg.get("company_name", ""))
        self.color_btn.set_color(cfg.get("primary_color", "#3B82F6"))

        self.lbl_sr.setText(cfg.get("label_sr", ""))
        self.lbl_open.setText(cfg.get("label_open", ""))
        self.lbl_in_progress.setText(cfg.get("label_in_progress", ""))
        self.lbl_completed.setText(cfg.get("label_completed", ""))
        self.lbl_closed.setText(cfg.get("label_closed", ""))

        mode = cfg.get("whatsapp_mode", "qr")
        idx  = 0 if mode == "qr" else 1
        self.wa_mode.setCurrentIndex(idx)
        self._on_wa_mode_change()

        self.meta_phone_id.setText(cfg.get("meta_phone_id", ""))
        self.meta_token.setText(cfg.get("meta_access_token", ""))
        self.report_time.setText(cfg.get("report_time", "09:00"))
        self.wa_template.setPlainText(cfg.get("whatsapp_template", ""))
        self.wa_number.setText(cfg.get("whatsapp_number", ""))

        self.smtp_email.setText(cfg.get("smtp_email", ""))
        self.smtp_password.setText(cfg.get("smtp_password", ""))
        self.email_template.setPlainText(cfg.get("email_template", ""))

        self.notify_sr_created.setChecked(cfg.get("notify_sr_created", "true") == "true")
        self.notify_sr_assigned.setChecked(cfg.get("notify_sr_assigned", "true") == "true")
        self.notify_step_done.setChecked(cfg.get("notify_step_done", "true") == "true")
        self.notify_sr_closed.setChecked(cfg.get("notify_sr_closed", "true") == "true")
        self.notify_daily_report.setChecked(cfg.get("notify_daily_report", "true") == "true")
        self.audit_enabled.setChecked(cfg.get("audit_enabled", "true") == "true")

    def _collect_data(self) -> dict:
        return {
            "app_name":           self.app_name.text().strip(),
            "company_name":       self.company_name.text().strip(),
            "primary_color":      self.color_btn.get_color(),
            "label_sr":           self.lbl_sr.text().strip(),
            "label_open":         self.lbl_open.text().strip(),
            "label_in_progress":  self.lbl_in_progress.text().strip(),
            "label_completed":    self.lbl_completed.text().strip(),
            "label_closed":       self.lbl_closed.text().strip(),
            "whatsapp_mode":      self.wa_mode.currentData(),
            "meta_phone_id":      self.meta_phone_id.text().strip(),
            "meta_access_token":  self.meta_token.text().strip(),
            "report_time":        self.report_time.text().strip(),
            "whatsapp_template":  self.wa_template.toPlainText().strip(),
            "whatsapp_number":    self.wa_number.text().strip(),
            "smtp_email":         self.smtp_email.text().strip(),
            "smtp_password":      self.smtp_password.text().strip(),
            "email_template":     self.email_template.toPlainText().strip(),
            "notify_sr_created":  "true" if self.notify_sr_created.isChecked() else "false",
            "notify_sr_assigned": "true" if self.notify_sr_assigned.isChecked() else "false",
            "notify_step_done":   "true" if self.notify_step_done.isChecked() else "false",
            "notify_sr_closed":   "true" if self.notify_sr_closed.isChecked() else "false",
            "notify_daily_report":"true" if self.notify_daily_report.isChecked() else "false",
            "audit_enabled":      "true" if self.audit_enabled.isChecked() else "false",
        }

    def _save(self):
        data = self._collect_data()

        rt = data.get("report_time", "")
        if rt and not validate_time(rt):
            QMessageBox.warning(self, "Validation", "Report Time must be HH:MM (e.g. 09:00)."); return

        self.save_btn.setEnabled(False); self.save_btn.setText("Saving…")
        self._worker = SaveSettingsWorker(data)
        self._worker.done.connect(self._on_saved)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_saved(self):
        self.save_btn.setEnabled(True); self.save_btn.setText("💾  Save All Settings")
        # Apply color live
        from services.config_service import global_config
        cfg = global_config.get()
        new_style = build_stylesheet(cfg.get("primary_color", "#3B82F6"))
        self.stylesheet_changed.emit(new_style)
        QMessageBox.information(self, "Saved", "Settings saved and applied.")

    def _on_error(self, msg: str):
        self.save_btn.setEnabled(True); self.save_btn.setText("💾  Save All Settings")
        QMessageBox.critical(self, "Save Failed", f"Could not save:\n{msg}")

    # ── WhatsApp mode toggle ──────────────────────────────────────────────────

    def _on_wa_mode_change(self):
        mode = self.wa_mode.currentData()
        self.qr_grp.setVisible(mode == "qr")
        self.meta_grp.setVisible(mode == "meta")

    def _preview_color(self, color: str):
        """Apply color change live to the whole app without saving."""
        new_style = build_stylesheet(color)
        self.stylesheet_changed.emit(new_style)

    # ── Test helpers ──────────────────────────────────────────────────────────

    def _test_wa_qr(self):
        from ui.whatsapp_qr_widget import SendTestDialog
        if self._wa_widget:
            dlg = SendTestDialog(self._wa_widget, self)
            dlg.exec()

    def _test_wa_meta(self):
        num = self.wa_number.text().strip()
        if not num:
            QMessageBox.warning(self, "No Number", "Set a Default Number first."); return
        try:
            from services.whatsapp_service import send_whatsapp_message
            # temporarily override mode
            global_config._config["whatsapp_mode"] = "meta"
            send_whatsapp_message(num, "✅ SR Manager: Meta WhatsApp test.")
            QMessageBox.information(self, "Sent", "Test message sent via Meta Cloud API.")
        except Exception as e:
            QMessageBox.critical(self, "Failed", str(e))

    def _test_email(self):
        from utils.auth import session
        from services.email_service import send_email
        to = session.email or ""
        if not to:
            QMessageBox.warning(self, "No Email", "Could not determine your email."); return
        try:
            send_email("SR Manager Test", "This is a test email from SR Manager.", to)
            QMessageBox.information(self, "Sent", f"Test email sent to {to}.")
        except Exception as e:
            QMessageBox.critical(self, "Failed", str(e))

    # ── Danger zone actions ───────────────────────────────────────────────────

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export SRs", "service_requests.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            from db import storage
            srs = storage.get_collection("service_requests")
            import csv
            keys = ["id", "title", "description", "status", "priority",
                    "type", "assigned_to", "created_by", "created_at", "updated_at"]
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(srs)
            QMessageBox.information(self, "Exported", f"Exported {len(srs)} SRs to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _reset_settings(self):
        if QMessageBox.question(self, "Reset Settings",
            "Reset ALL settings to their defaults? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            from services.config_service import DEFAULT_CONFIG
            global_config.save(DEFAULT_CONFIG)
            self._load_values()
            QMessageBox.information(self, "Reset", "Settings reset to defaults.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _wipe_srs(self):
        reply = QMessageBox.warning(
            self, "⚠ WIPE ALL SRs",
            "This will PERMANENTLY DELETE every service request.\n\n"
            "Type 'DELETE' in the next dialog to confirm.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Ok:
            return

        from PyQt6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, "Confirm Wipe", "Type DELETE to confirm:")
        if not ok or text.strip() != "DELETE":
            QMessageBox.information(self, "Cancelled", "Wipe cancelled.")
            return

        try:
            from db import storage
            srs = storage.get_collection("service_requests")
            for sr in srs:
                storage.delete_document("service_requests", sr["id"])
            QMessageBox.information(self, "Done", f"Deleted {len(srs)} service requests.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
