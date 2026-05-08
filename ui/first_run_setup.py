# ui/first_run_setup.py
"""
First-Run Setup Dialog.

Shown once on startup when no users exist in the database.
Replaces the hardcoded bootstrap admin credential in db.py.
Writes the admin user to local storage and creates global_config defaults.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QCheckBox, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont

from utils.helpers import validate_email, validate_password


class SetupWorker(QThread):
    done  = pyqtSignal(str, str, str)   # uid, email, name
    error = pyqtSignal(str)

    def __init__(self, name: str, email: str, password: str,
                 company: str, app_name: str):
        super().__init__()
        self.name     = name
        self.email    = email
        self.password = password
        self.company  = company
        self.app_name = app_name

    def run(self):
        try:
            from services.encryption_service import encryption_service
            from services.local_storage_service import local_storage
            from utils.helpers import utc_now_iso

            uid = "local-admin"

            # Create the master admin user
            local_storage.create_document("users", {
                "uid":             uid,
                "email":           self.email,
                "name":            self.name,
                "role":            "admin",
                "whatsapp_number": "",
                "active":          True,
                "is_master_admin": True,   # cannot be deleted/disabled
                "password_hash":   encryption_service.hash_password(self.password),
                "created_at":      utc_now_iso(),
            }, doc_id=uid)

            # Write initial global config
            from services.config_service import global_config, DEFAULT_CONFIG
            cfg = DEFAULT_CONFIG.copy()
            cfg["company_name"] = self.company
            cfg["app_name"]     = self.app_name
            try:
                from db import storage
                storage.create_document("settings", cfg, doc_id="global_config")
            except Exception:
                pass
            global_config.reload()

            from services.audit_service import log_action
            log_action("first_run_setup",
                       f"Admin account created for {self.email}",
                       uid)

            self.done.emit(uid, self.email, self.name)

        except Exception as e:
            self.error.emit(str(e))


class FirstRunSetupDialog(QDialog):
    """
    Modal dialog shown on first launch.
    Returns QDialog.Accepted when setup completes successfully.
    """

    setup_complete = pyqtSignal(str, str, str)   # uid, email, name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SR Manager — First Time Setup")
        self.setFixedWidth(500)
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.CustomizeWindowHint
        )
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)

        # ── Header ─────────────────────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet("background: #1E293B; padding: 0px;")
        header.setFixedHeight(110)
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(32, 20, 32, 20)
        h_lay.setSpacing(4)

        icon_lbl = QLabel("🛠")
        icon_lbl.setStyleSheet("font-size: 32px; color: white; background: transparent;")
        h_lay.addWidget(icon_lbl)

        title = QLabel("Welcome — Let's set up SR Manager")
        title.setStyleSheet(
            "font-size: 17px; font-weight: bold; color: white; background: transparent;"
        )
        h_lay.addWidget(title)

        sub = QLabel("Create your admin account to get started.")
        sub.setStyleSheet(
            "font-size: 12px; color: #94A3B8; background: transparent;"
        )
        h_lay.addWidget(sub)
        lay.addWidget(header)

        # ── Body ────────────────────────────────────────────────────────────
        body = QFrame()
        body.setStyleSheet("""
            QFrame { background: #FFFFFF; }
            QLabel { color: #1E293B; background: transparent; font-size: 12px; }
            QLineEdit {
                background: #F8FAFC; color: #1E293B;
                border: 1.5px solid #CBD5E1; border-radius: 6px;
                padding: 0 12px; font-size: 13px;
            }
            QLineEdit:focus { background: #FFFFFF; border-color: #3B82F6; }
            QCheckBox { color: #64748B; font-size: 12px; background: transparent; }
        """)
        b_lay = QVBoxLayout(body)
        b_lay.setContentsMargins(32, 28, 32, 28)
        b_lay.setSpacing(14)

        # Company / App Name row
        row1 = QHBoxLayout(); row1.setSpacing(12)
        app_col  = QVBoxLayout(); app_col.setSpacing(4)
        app_col.addWidget(self._label("App Name"))
        self.app_name_input = QLineEdit("SR Manager")
        self.app_name_input.setFixedHeight(38)
        app_col.addWidget(self.app_name_input)

        company_col = QVBoxLayout(); company_col.setSpacing(4)
        company_col.addWidget(self._label("Company Name"))
        self.company_input = QLineEdit()
        self.company_input.setPlaceholderText("Your Company Ltd.")
        self.company_input.setFixedHeight(38)
        company_col.addWidget(self.company_input)

        row1.addLayout(app_col)
        row1.addLayout(company_col)
        b_lay.addLayout(row1)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #E2E8F0; margin: 4px 0;")
        b_lay.addWidget(divider)

        lbl_section = QLabel("Admin Account")
        lbl_section.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #64748B; letter-spacing: 1px;"
        )
        b_lay.addWidget(lbl_section)

        # Full name
        b_lay.addWidget(self._label("Your Full Name *"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Sidharth Kumar")
        self.name_input.setFixedHeight(38)
        b_lay.addWidget(self.name_input)

        # Email
        b_lay.addWidget(self._label("Admin Email *"))
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("admin@yourcompany.com")
        self.email_input.setFixedHeight(38)
        b_lay.addWidget(self.email_input)

        # Password row
        pwd_row = QHBoxLayout(); pwd_row.setSpacing(12)

        pwd_col = QVBoxLayout(); pwd_col.setSpacing(4)
        pwd_col.addWidget(self._label("Password *  (min 8 chars)"))
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setPlaceholderText("••••••••••")
        self.pwd_input.setFixedHeight(38)
        pwd_col.addWidget(self.pwd_input)

        confirm_col = QVBoxLayout(); confirm_col.setSpacing(4)
        confirm_col.addWidget(self._label("Confirm Password *"))
        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input.setPlaceholderText("••••••••••")
        self.confirm_input.setFixedHeight(38)
        confirm_col.addWidget(self.confirm_input)

        pwd_row.addLayout(pwd_col)
        pwd_row.addLayout(confirm_col)
        b_lay.addLayout(pwd_row)

        self.show_pwd = QCheckBox("Show password")
        self.show_pwd.setStyleSheet("font-size: 12px; color: #64748B;")
        self.show_pwd.toggled.connect(self._toggle_pwd_visibility)
        b_lay.addWidget(self.show_pwd)

        # Error label
        self.err_lbl = QLabel("")
        self.err_lbl.setStyleSheet(
            "color: #EF4444; font-size: 12px; background: #FEF2F2;"
            "border-radius: 6px; padding: 8px 12px;"
        )
        self.err_lbl.setWordWrap(True)
        self.err_lbl.setVisible(False)
        b_lay.addWidget(self.err_lbl)

        # Progress bar (shown during setup)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)   # indeterminate
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        b_lay.addWidget(self.progress)

        # Submit button
        self.submit_btn = QPushButton("Create Admin Account & Launch")
        self.submit_btn.setObjectName("btn_primary")
        self.submit_btn.setFixedHeight(44)
        font = self.submit_btn.font()
        font.setBold(True)
        self.submit_btn.setFont(font)
        self.submit_btn.clicked.connect(self._submit)
        b_lay.addWidget(self.submit_btn)

        note = QLabel(
            "This admin account cannot be deleted. "
            "Additional users can be created from the Admin dashboard."
        )
        note.setWordWrap(True)
        note.setStyleSheet("font-size: 11px; color: #94A3B8;")
        b_lay.addWidget(note)

        lay.addWidget(body)

    @staticmethod
    def _label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #374151;")
        return lbl

    def _toggle_pwd_visibility(self, show: bool):
        mode = QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password
        self.pwd_input.setEchoMode(mode)
        self.confirm_input.setEchoMode(mode)

    def _submit(self):
        name     = self.name_input.text().strip()
        email    = self.email_input.text().strip()
        pwd      = self.pwd_input.text()
        confirm  = self.confirm_input.text()
        company  = self.company_input.text().strip() or "My Company"
        app_name = self.app_name_input.text().strip() or "SR Manager"

        if not name:
            return self._err("Full name is required.")
        if not validate_email(email):
            return self._err("Please enter a valid email address.")
        if len(pwd) < 8:
            return self._err("Password must be at least 8 characters.")
        if pwd != confirm:
            return self._err("Passwords do not match.")

        self._set_busy(True)
        self._worker = SetupWorker(name, email, pwd, company, app_name)
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    @pyqtSlot(str, str, str)
    def _on_done(self, uid: str, email: str, name: str):
        self._set_busy(False)
        self.setup_complete.emit(uid, email, name)
        self.accept()

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self._set_busy(False)
        self._err(f"Setup failed: {msg}")

    def _err(self, msg: str):
        self.err_lbl.setText(f"⚠  {msg}")
        self.err_lbl.setVisible(True)

    def _set_busy(self, busy: bool):
        self.submit_btn.setEnabled(not busy)
        self.submit_btn.setText(
            "Setting up…" if busy else "Create Admin Account & Launch"
        )
        self.progress.setVisible(busy)
        self.err_lbl.setVisible(False)
        for w in (self.name_input, self.email_input,
                  self.pwd_input, self.confirm_input,
                  self.company_input, self.app_name_input):
            w.setEnabled(not busy)


def needs_first_run_setup() -> bool:
    """Return True if no users exist yet (first launch)."""
    try:
        from services.local_storage_service import local_storage
        return len(local_storage.get_collection("users")) == 0
    except Exception:
        return False
