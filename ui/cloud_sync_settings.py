# ui/cloud_sync_settings.py
"""
Cloud Sync & Microsoft Login Settings Tab.
Injected into AdminSettingsPanel as a new "☁ Cloud Sync" tab.

Features:
  - Supabase URL / Key configuration
  - Enable/disable sync toggle
  - Live connection test
  - Sync now button with result display
  - Microsoft Login (Azure) Client ID / Tenant ID
  - Configurable overdue SLA days (Phase 1 fix)
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QFormLayout, QCheckBox,
    QSpinBox, QFrame, QMessageBox, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot


class CloudSyncSettingsPanel(QWidget):
    """
    Self-contained panel. Can be embedded in any QTabWidget.
    Emits settings_changed(dict) when saved.
    """
    settings_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(16)

        # ── Supabase group ────────────────────────────────────────────────────
        sb_grp = QGroupBox("☁  Supabase — Cloud Database")
        sb_grp.setStyleSheet("QGroupBox { font-weight: bold; }")
        sf = QFormLayout(sb_grp); sf.setSpacing(10)

        self.sync_enabled = QCheckBox("Enable cloud sync")
        self.sync_enabled.setToolTip(
            "When enabled, local changes are pushed to Supabase on 'Sync Now' "
            "and automatically on app events."
        )
        sf.addRow("", self.sync_enabled)

        self.sb_url = QLineEdit()
        self.sb_url.setPlaceholderText("https://xxxxxxxxxxxx.supabase.co")
        self.sb_url.setFixedHeight(36)
        sf.addRow("Project URL", self.sb_url)

        self.sb_key = QLineEdit()
        self.sb_key.setPlaceholderText("eyJhbGciOiJIUzI1NiIsInR5cCI6...")
        self.sb_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.sb_key.setFixedHeight(36)
        sf.addRow("Supabase API Key", self.sb_key)

        show_key = QCheckBox("Show key")
        show_key.toggled.connect(
            lambda v: self.sb_key.setEchoMode(
                QLineEdit.EchoMode.Normal if v else QLineEdit.EchoMode.Password
            )
        )
        sf.addRow("", show_key)

        # Buttons row
        btn_row = QHBoxLayout()
        self.test_btn = QPushButton("🔌 Test Connection")
        self.test_btn.setObjectName("btn_secondary")
        self.test_btn.setFixedHeight(36)
        self.test_btn.clicked.connect(self._test_connection)
        btn_row.addWidget(self.test_btn)

        self.sync_btn = QPushButton("⚡ Sync Now")
        self.sync_btn.setObjectName("btn_primary")
        self.sync_btn.setFixedHeight(36)
        self.sync_btn.clicked.connect(self._sync_now)
        btn_row.addWidget(self.sync_btn)

        self.full_sync_btn = QPushButton("🔄 Full Sync (Push + Pull)")
        self.full_sync_btn.setObjectName("btn_secondary")
        self.full_sync_btn.setFixedHeight(36)
        self.full_sync_btn.clicked.connect(self._full_sync)
        btn_row.addWidget(self.full_sync_btn)

        sf.addRow("", btn_row)

        # Status display
        self.status_box = QTextEdit()
        self.status_box.setReadOnly(True)
        self.status_box.setFixedHeight(80)
        self.status_box.setPlaceholderText("Connection status will appear here…")
        self.status_box.setStyleSheet(
            "background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; "
            "font-family: 'Consolas', monospace; font-size: 12px;"
        )
        sf.addRow("Status", self.status_box)

        note = QLabel(
            "ℹ  Run <b>setup/supabase_schema.sql</b> in Supabase SQL Editor before enabling sync. "
            "Prefer a least-privilege key/policy for your deployment and never commit keys."
        )
        note.setWordWrap(True)
        note.setStyleSheet("font-size: 11px; color: #64748B;")
        sf.addRow("", note)

        lay.addWidget(sb_grp)

        # ── Microsoft Login group ─────────────────────────────────────────────
        ms_grp = QGroupBox("🔐  Microsoft Login (Azure AD)")
        ms_grp.setStyleSheet("QGroupBox { font-weight: bold; }")
        mf = QFormLayout(ms_grp); mf.setSpacing(10)

        self.azure_client_id = QLineEdit()
        self.azure_client_id.setPlaceholderText("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        self.azure_client_id.setFixedHeight(36)
        mf.addRow("Application (Client) ID", self.azure_client_id)

        self.azure_tenant_id = QLineEdit()
        self.azure_tenant_id.setPlaceholderText("common  (or your org's tenant ID)")
        self.azure_tenant_id.setFixedHeight(36)
        mf.addRow("Tenant ID", self.azure_tenant_id)

        ms_note = QLabel(
            "ℹ  Register your app at <b>portal.azure.com → App Registrations</b>. "
            "Set Redirect URI to <code>http://localhost</code> under Mobile/Desktop platform. "
            "New Microsoft login users are assigned the <b>viewer</b> role — elevate in Users tab."
        )
        ms_note.setWordWrap(True)
        ms_note.setStyleSheet("font-size: 11px; color: #64748B;")
        mf.addRow("", ms_note)

        test_ms_btn = QPushButton("🔑 Test Microsoft Login")
        test_ms_btn.setObjectName("btn_secondary")
        test_ms_btn.setFixedHeight(36)
        test_ms_btn.clicked.connect(self._test_ms_login)
        mf.addRow("", test_ms_btn)

        lay.addWidget(ms_grp)

        # ── SLA / Overdue group ───────────────────────────────────────────────
        sla_grp = QGroupBox("⏱  SLA Settings")
        sla_grp.setStyleSheet("QGroupBox { font-weight: bold; }")
        slaf = QFormLayout(sla_grp); slaf.setSpacing(10)

        self.overdue_days = QSpinBox()
        self.overdue_days.setRange(1, 365)
        self.overdue_days.setValue(3)
        self.overdue_days.setSuffix("  days")
        self.overdue_days.setFixedHeight(36)
        self.overdue_days.setFixedWidth(120)
        slaf.addRow("Overdue threshold", self.overdue_days)

        sla_note = QLabel(
            "SRs open longer than this threshold are marked as overdue in stats and dashboards."
        )
        sla_note.setWordWrap(True)
        sla_note.setStyleSheet("font-size: 11px; color: #64748B;")
        slaf.addRow("", sla_note)

        lay.addWidget(sla_grp)

        # ── Save button ───────────────────────────────────────────────────────
        save_row = QHBoxLayout()
        save_row.addStretch()
        self.save_btn = QPushButton("💾 Save Cloud & SLA Settings")
        self.save_btn.setObjectName("btn_primary")
        self.save_btn.setFixedHeight(40)
        self.save_btn.setMinimumWidth(220)
        self.save_btn.clicked.connect(self._save)
        save_row.addWidget(self.save_btn)
        lay.addLayout(save_row)

        lay.addStretch()

    def _load_values(self):
        from services.config_service import global_config
        cfg = global_config.get()
        self.sync_enabled.setChecked(cfg.get("sync_enabled", "false") == "true")
        self.sb_url.setText(cfg.get("supabase_url", ""))
        self.sb_key.setText(cfg.get("supabase_key", ""))
        self.azure_client_id.setText(cfg.get("azure_client_id", ""))
        self.azure_tenant_id.setText(cfg.get("azure_tenant_id", "common"))
        try:
            self.overdue_days.setValue(int(cfg.get("overdue_days", "3")))
        except (ValueError, TypeError):
            self.overdue_days.setValue(3)

    def _collect(self) -> dict:
        return {
            "sync_enabled":    "true" if self.sync_enabled.isChecked() else "false",
            "supabase_url":    self.sb_url.text().strip(),
            "supabase_key":    self.sb_key.text().strip(),
            "azure_client_id": self.azure_client_id.text().strip(),
            "azure_tenant_id": self.azure_tenant_id.text().strip() or "common",
            "overdue_days":    str(self.overdue_days.value()),
        }

    def _save(self):
        from services.config_service import global_config
        from services.supabase_service import supabase_service
        data = self._collect()
        try:
            global_config.save({**global_config.get(), **data})
            supabase_service.reset_client()   # force re-init with new credentials
            self.settings_changed.emit(data)
            self._set_status("✅ Settings saved.", success=True)
        except Exception as e:
            self._set_status(f"❌ Save failed: {e}", success=False)

    def _test_connection(self):
        from services.supabase_service import supabase_service
        from services.sync_service import ConnectionTestWorker

        # Apply current field values temporarily
        url = self.sb_url.text().strip()
        key = self.sb_key.text().strip()
        if not url or not key:
            self._set_status("⚠ Enter Supabase URL and Key first.", success=False)
            return

        from services.config_service import global_config
        global_config._config["supabase_url"] = url
        global_config._config["supabase_key"] = key
        supabase_service.reset_client()

        self.test_btn.setEnabled(False)
        self.test_btn.setText("Testing…")
        self._set_status("Connecting to Supabase…")

        worker = ConnectionTestWorker()
        worker.done.connect(self._on_connection_test)
        worker.finished.connect(lambda: self.test_btn.setEnabled(True))
        worker.finished.connect(lambda: self.test_btn.setText("🔌 Test Connection"))
        self._workers.append(worker)
        worker.start()

    @pyqtSlot(bool, str)
    def _on_connection_test(self, ok: bool, msg: str):
        prefix = "✅" if ok else "❌"
        self._set_status(f"{prefix} {msg}", success=ok)

    def _sync_now(self):
        from services.sync_service import SyncNowWorker
        self.sync_btn.setEnabled(False)
        self.sync_btn.setText("Syncing…")
        self._set_status("Pushing local changes to Supabase…")

        worker = SyncNowWorker()
        worker.done.connect(self._on_sync_done)
        worker.error.connect(lambda e: self._set_status(f"❌ {e}", success=False))
        worker.finished.connect(lambda: self.sync_btn.setEnabled(True))
        worker.finished.connect(lambda: self.sync_btn.setText("⚡ Sync Now"))
        self._workers.append(worker)
        worker.start()

    def _full_sync(self):
        from services.sync_service import FullSyncWorker
        self.full_sync_btn.setEnabled(False)
        self.full_sync_btn.setText("Syncing…")
        self._set_status("Full sync started…")

        worker = FullSyncWorker()
        worker.progress.connect(lambda msg: self._set_status(msg))
        worker.done.connect(self._on_sync_done)
        worker.error.connect(lambda e: self._set_status(f"❌ {e}", success=False))
        worker.finished.connect(lambda: self.full_sync_btn.setEnabled(True))
        worker.finished.connect(lambda: self.full_sync_btn.setText("🔄 Full Sync (Push + Pull)"))
        self._workers.append(worker)
        worker.start()

    @pyqtSlot(dict)
    def _on_sync_done(self, result: dict):
        ok  = result.get("ok", False)
        msg = result.get("message", "")
        pushed  = result.get("pushed", 0)
        pulled  = result.get("pulled", 0)
        failed  = result.get("failed", 0)
        detail  = f"Pushed: {pushed}  |  Pulled: {pulled}  |  Failed: {failed}"
        prefix  = "✅" if ok else "⚠"
        self._set_status(f"{prefix} {msg}\n{detail}", success=ok)

    def _test_ms_login(self):
        from services.auth_service import microsoft_auth
        client_id = self.azure_client_id.text().strip()
        if not client_id:
            QMessageBox.warning(self, "Missing", "Enter an Azure Client ID first.")
            return
        # Temporarily apply config
        from services.config_service import global_config
        global_config._config["azure_client_id"] = client_id
        global_config._config["azure_tenant_id"] = (
            self.azure_tenant_id.text().strip() or "common"
        )
        microsoft_auth.reset_client() if hasattr(microsoft_auth, "reset_client") else None

        from services.auth_service import MicrosoftLoginWorker
        self._ms_worker = MicrosoftLoginWorker(mode="interactive")
        self._ms_worker.success.connect(
            lambda email, name, oid:
                QMessageBox.information(self, "Login Successful",
                    f"✅ Microsoft Login works!\n\nUser: {name}\nEmail: {email}")
        )
        self._ms_worker.error.connect(
            lambda msg: QMessageBox.critical(self, "Login Failed", f"❌ {msg}")
        )
        self._ms_worker.start()

    def _set_status(self, msg: str, success: bool | None = None):
        color = "#1E293B"
        if success is True:
            color = "#166534"
        elif success is False:
            color = "#991B1B"
        self.status_box.setStyleSheet(
            f"background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; "
            f"font-family: 'Consolas', monospace; font-size: 12px; color: {color};"
        )
        self.status_box.setPlainText(msg)
