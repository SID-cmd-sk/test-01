# ui/login.py
"""
Login Screen — email/password + Microsoft Login button.

Phase 3 addition: Microsoft Login button appears when azure_client_id
is configured in Admin Settings → Cloud Sync. If not configured it is
hidden, so the UI is clean for non-Azure deployments.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QDialog, QTextBrowser
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from db import storage, LocalAuthError, LocalNetworkError
from utils.helpers import validate_email


# ── Workers ───────────────────────────────────────────────────────────────────

class LoginWorker(QThread):
    success = pyqtSignal(dict, dict)
    error   = pyqtSignal(str)

    def __init__(self, email: str, password: str):
        super().__init__()
        self.email    = email
        self.password = password

    def run(self):
        try:
            auth     = storage.login(self.email, self.password)
            user_doc = storage.get_document("users", auth["uid"])
            if not user_doc:
                self.error.emit(
                    "Your account exists but is not in the user database.\n"
                    "Contact your administrator.")
                return
            role = user_doc.get("role", "technical")
            try:
                role_doc = (storage.get_document("role_overrides", role) or
                            storage.get_document("roles", role))
            except Exception:
                role_doc = None
            user_doc["_role_doc"] = role_doc
            self.success.emit(auth, user_doc)
        except (LocalAuthError, LocalNetworkError) as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Unexpected error: {e}")


class MicrosoftLoginWorkerWrapper(QThread):
    """Thin wrapper — delegates to services/auth_service.py."""
    success = pyqtSignal(str, str, str, str)   # uid, email, name, role
    code_needed = pyqtSignal(str, str, str)    # url, code, message
    error   = pyqtSignal(str)

    def run(self):
        try:
            from services.auth_service import MicrosoftLoginWorker
            # Use device-code so no browser redirect issues on Windows desktop
            inner = MicrosoftLoginWorker(mode="device_code")
            inner.device_code.connect(self.code_needed)
            inner.error.connect(self.error)

            def _on_success(email: str, name: str, oid: str):
                # Look up the local user record
                uid  = ""
                role = "viewer"
                try:
                    for u in storage.get_collection("users"):
                        if u.get("email", "").strip().lower() == email.strip().lower():
                            uid  = str(u.get("uid") or u.get("id", ""))
                            role = u.get("role", "viewer")
                            break
                except Exception:
                    pass
                self.success.emit(uid or oid, email, name, role)

            inner.success.connect(_on_success)
            inner.run()   # run synchronously inside this thread
        except Exception as e:
            self.error.emit(str(e))


# ── Device-code dialog ────────────────────────────────────────────────────────

class DeviceCodeDialog(QDialog):
    """Shows the Microsoft device-code flow URL + code in a small dialog."""

    def __init__(self, url: str, code: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Microsoft Login — Device Code")
        self.setFixedWidth(440)
        self.setModal(True)

        lay = QVBoxLayout(self)
        lay.setSpacing(16)
        lay.setContentsMargins(28, 28, 28, 28)

        icon = QLabel("🔐")
        icon.setStyleSheet("font-size: 36px;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(icon)

        ttl = QLabel("Sign in with Microsoft")
        ttl.setStyleSheet("font-size: 17px; font-weight: bold; color: #0F172A;")
        ttl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(ttl)

        inst = QLabel(
            "Open the link below in your browser and enter the code to sign in.\n"
            "This dialog will close automatically when you're done."
        )
        inst.setWordWrap(True)
        inst.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inst.setStyleSheet("color: #64748B; font-size: 12px;")
        lay.addWidget(inst)

        # URL
        url_lbl = QLabel(f'<a href="{url}">{url}</a>')
        url_lbl.setOpenExternalLinks(True)
        url_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        url_lbl.setStyleSheet("font-size: 13px;")
        lay.addWidget(url_lbl)

        # Code box
        code_frame = QFrame()
        code_frame.setStyleSheet(
            "background: #EFF6FF; border-radius: 10px; padding: 6px;"
        )
        cf = QVBoxLayout(code_frame)
        code_disp = QLabel(code)
        code_disp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        code_disp.setStyleSheet(
            "font-size: 32px; font-weight: bold; letter-spacing: 8px; "
            "color: #1D4ED8; font-family: 'Consolas', monospace;"
        )
        copy_btn = QPushButton("Copy Code")
        copy_btn.setObjectName("btn_secondary")
        copy_btn.setFixedHeight(32)
        copy_btn.clicked.connect(lambda: (
            __import__("PyQt6.QtWidgets", fromlist=["QApplication"])
            .QApplication.clipboard().setText(code)
        ))
        cf.addWidget(code_disp)
        cf.addWidget(copy_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(code_frame)

        waiting = QLabel("⏳ Waiting for you to complete sign-in in your browser…")
        waiting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        waiting.setStyleSheet("font-size: 12px; color: #64748B;")
        lay.addWidget(waiting)

        cancel = QPushButton("Cancel")
        cancel.setObjectName("btn_secondary")
        cancel.clicked.connect(self.reject)
        lay.addWidget(cancel, alignment=Qt.AlignmentFlag.AlignCenter)


# ── Login Screen ──────────────────────────────────────────────────────────────

class LoginScreen(QWidget):
    login_success = pyqtSignal(str, str, str, str)   # uid, email, name, role

    def __init__(self):
        super().__init__()
        self._worker      = None
        self._ms_worker   = None
        self._code_dialog = None
        self._build_ui()

    def _build_ui(self):
        from services.config_service import global_config
        cfg = global_config.get()

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.setContentsMargins(0, 0, 0, 0)

        bg = QFrame()
        bg.setStyleSheet("background-color: #F1F5F9;")
        bg_lay = QVBoxLayout(bg)
        bg_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("login_card")
        card.setFixedWidth(420)
        card_lay = QVBoxLayout(card)
        card_lay.setSpacing(14)
        card_lay.setContentsMargins(40, 40, 40, 40)

        # ── Branding ──────────────────────────────────────────────────────────
        icon = QLabel("🛠")
        icon.setStyleSheet("font-size: 40px;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(icon)

        ttl = QLabel(cfg.get("app_name", "SR Manager"))
        ttl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ttl.setStyleSheet("font-size: 24px; font-weight: bold; color: #0F172A;")
        card_lay.addWidget(ttl)

        sub = QLabel(cfg.get("company_name", "Service Request Management"))
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("font-size: 12px; color: #64748B;")
        card_lay.addWidget(sub)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: #E2E8F0;")
        card_lay.addWidget(div)

        # ── Microsoft Login button (shown only if Azure is configured) ────────
        self.ms_btn = QPushButton("  Sign in with Microsoft")
        self.ms_btn.setFixedHeight(44)
        self.ms_btn.setStyleSheet("""
            QPushButton {
                background: #0078D4;
                color: white;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                border: none;
                padding-left: 12px;
            }
            QPushButton:hover   { background: #006BBE; }
            QPushButton:pressed { background: #005A9E; }
            QPushButton:disabled { background: #93C5FD; }
        """)
        # Prepend Microsoft icon (Unicode)
        self.ms_btn.setText("⊞  Sign in with Microsoft")
        self.ms_btn.clicked.connect(self._do_microsoft_login)
        card_lay.addWidget(self.ms_btn)

        # Divider "or"
        self._or_row = QFrame()
        or_lay = QHBoxLayout(self._or_row)
        or_lay.setContentsMargins(0, 0, 0, 0)
        line1 = QFrame(); line1.setFrameShape(QFrame.Shape.HLine)
        line1.setStyleSheet("color: #E2E8F0;")
        line2 = QFrame(); line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet("color: #E2E8F0;")
        or_lbl = QLabel("or")
        or_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        or_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        or_lbl.setFixedWidth(30)
        or_lay.addWidget(line1, 1)
        or_lay.addWidget(or_lbl)
        or_lay.addWidget(line2, 1)
        card_lay.addWidget(self._or_row)

        # Hide MS button + divider if Azure not configured
        self._refresh_ms_visibility(cfg)

        # ── Email / password form ─────────────────────────────────────────────
        card_lay.addWidget(self._lbl("Email Address"))
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("you@company.com")
        self.email_input.setFixedHeight(40)
        card_lay.addWidget(self.email_input)

        card_lay.addWidget(self._lbl("Password"))
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setPlaceholderText("••••••••")
        self.pwd_input.setFixedHeight(40)
        card_lay.addWidget(self.pwd_input)

        self.error_lbl = QLabel("")
        self.error_lbl.setObjectName("error_label")
        self.error_lbl.setWordWrap(True)
        self.error_lbl.setVisible(False)
        card_lay.addWidget(self.error_lbl)

        self.login_btn = QPushButton("Sign In")
        self.login_btn.setObjectName("btn_primary")
        self.login_btn.setFixedHeight(42)
        self.login_btn.clicked.connect(self._do_login)
        card_lay.addWidget(self.login_btn)

        self.pwd_input.returnPressed.connect(self._do_login)
        self.email_input.returnPressed.connect(lambda: self.pwd_input.setFocus())

        footer = QLabel(
            f"© {cfg.get('company_name','SR Manager')}  •  All roles require admin setup"
        )
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("font-size: 10px; color: #94A3B8;")
        card_lay.addWidget(footer)

        bg_lay.addWidget(card)
        outer.addWidget(bg)

    def _refresh_ms_visibility(self, cfg: dict | None = None):
        from services.config_service import global_config
        if cfg is None:
            cfg = global_config.get()
        has_azure = bool(cfg.get("azure_client_id", "").strip())
        self.ms_btn.setVisible(has_azure)
        self._or_row.setVisible(has_azure)

    @staticmethod
    def _lbl(text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet("font-size: 12px; font-weight: 600; color: #374151;")
        return l

    # ── Email login ───────────────────────────────────────────────────────────

    def _do_login(self):
        email = self.email_input.text().strip()
        pwd   = self.pwd_input.text()
        if not email or not pwd:
            self._show_error("Please enter your email and password.")
            return
        if not validate_email(email):
            self._show_error("Please enter a valid email address.")
            return
        self._set_loading(True)
        self._worker = LoginWorker(email, pwd)
        self._worker.success.connect(self._on_success)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    @pyqtSlot(dict, dict)
    def _on_success(self, auth: dict, user_doc: dict):
        self._set_loading(False)
        from utils.auth import session, DEFAULT_PERMISSIONS
        role     = user_doc.get("role", "technical")
        role_doc = user_doc.pop("_role_doc", None)
        perms    = (role_doc.get("permissions") if role_doc else None) or \
                   DEFAULT_PERMISSIONS.get(role, [])
        session.set(
            uid         = auth["uid"],
            email       = auth["email"],
            name        = user_doc.get("name", auth["email"].split("@")[0]),
            role        = role,
            whatsapp    = user_doc.get("whatsapp_number", ""),
            permissions = perms,
            role_doc    = role_doc,
        )
        self.login_success.emit(auth["uid"], auth["email"], session.name, role)

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self._set_loading(False)
        self._show_error(msg)

    # ── Microsoft Login ───────────────────────────────────────────────────────

    def _do_microsoft_login(self):
        self._set_loading(True, ms=True)
        self._ms_worker = MicrosoftLoginWorkerWrapper()
        self._ms_worker.success.connect(self._on_ms_success)
        self._ms_worker.code_needed.connect(self._show_device_code)
        self._ms_worker.error.connect(self._on_ms_error)
        self._ms_worker.finished.connect(lambda: self._set_loading(False, ms=True))
        self._ms_worker.start()

    @pyqtSlot(str, str, str)
    def _show_device_code(self, url: str, code: str, message: str):
        self._code_dialog = DeviceCodeDialog(url, code, message, self)
        self._code_dialog.show()

    @pyqtSlot(str, str, str, str)
    def _on_ms_success(self, uid: str, email: str, name: str, role: str):
        if self._code_dialog:
            self._code_dialog.accept()
            self._code_dialog = None
        from utils.auth import session, DEFAULT_PERMISSIONS
        session.set(
            uid         = uid,
            email       = email,
            name        = name,
            role        = role,
            permissions = DEFAULT_PERMISSIONS.get(role, []),
        )
        self.login_success.emit(uid, email, name, role)

    @pyqtSlot(str)
    def _on_ms_error(self, msg: str):
        if self._code_dialog:
            self._code_dialog.reject()
            self._code_dialog = None
        self._show_error(f"Microsoft login failed: {msg}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _show_error(self, msg: str):
        self.error_lbl.setText(f"⚠  {msg}")
        self.error_lbl.setVisible(True)

    def _set_loading(self, loading: bool, ms: bool = False):
        self.error_lbl.setVisible(False)
        self.login_btn.setEnabled(not loading)
        self.email_input.setEnabled(not loading)
        self.pwd_input.setEnabled(not loading)
        self.ms_btn.setEnabled(not loading)
        if ms:
            self.ms_btn.setText("⏳  Signing in with Microsoft…" if loading else "⊞  Sign in with Microsoft")
            self.login_btn.setText("Sign In")
        else:
            self.login_btn.setText("Signing in…" if loading else "Sign In")
            self.ms_btn.setText("⊞  Sign in with Microsoft")
