# ui/login.py
"""
Login Screen — email + password only.
Microsoft/Azure login removed (would require paid Azure subscription).
All authentication is via local JSON database with PBKDF2 hashed passwords.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from db import storage, LocalAuthError
from utils.helpers import validate_email


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
                self.error.emit("Account found but not in user database. Contact admin.")
                return
            role = user_doc.get("role", "technical")
            try:
                role_doc = (storage.get_document("role_overrides", role) or
                            storage.get_document("roles", role))
            except Exception:
                role_doc = None
            user_doc["_role_doc"] = role_doc
            self.success.emit(auth, user_doc)
        except LocalAuthError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Unexpected error: {e}")


class LoginScreen(QWidget):
    login_success = pyqtSignal(str, str, str, str)   # uid, email, name, role

    def __init__(self):
        super().__init__()
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        from services.config_service import global_config
        cfg = global_config.get()

        # Full-screen background
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        bg = QFrame()
        bg.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #1E293B, stop:1 #0F172A);")
        bg_lay = QVBoxLayout(bg)
        bg_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bg_lay.setContentsMargins(0, 0, 0, 0)

        # ── Card ──────────────────────────────────────────────────────────────
        card = QFrame()
        card.setObjectName("login_card")
        card.setFixedWidth(440)
        card.setStyleSheet("""
            QFrame#login_card {
                background: #FFFFFF;
                border-radius: 16px;
                border: none;
            }
        """)
        card_lay = QVBoxLayout(card)
        card_lay.setSpacing(0)
        card_lay.setContentsMargins(0, 0, 0, 0)

        # Card top accent bar
        accent = QFrame()
        accent.setFixedHeight(6)
        primary = cfg.get("primary_color", "#3B82F6")
        accent.setStyleSheet(f"background: {primary}; border-top-left-radius: 16px; border-top-right-radius: 16px;")
        card_lay.addWidget(accent)

        # Card body
        body = QFrame()
        body.setStyleSheet("background: transparent;")
        body_lay = QVBoxLayout(body)
        body_lay.setSpacing(14)
        body_lay.setContentsMargins(40, 36, 40, 40)

        # Icon + title
        icon = QLabel("🛠")
        icon.setStyleSheet("font-size: 44px; background: transparent; color: #1E293B;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body_lay.addWidget(icon)

        ttl = QLabel(cfg.get("app_name", "SR Manager"))
        ttl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ttl.setStyleSheet(f"font-size: 26px; font-weight: bold; color: #0F172A; background: transparent;")
        body_lay.addWidget(ttl)

        sub = QLabel(cfg.get("company_name", "Service Request Management"))
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("font-size: 12px; color: #64748B; background: transparent;")
        body_lay.addWidget(sub)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("background: #E2E8F0; max-height: 1px; margin: 4px 0;")
        body_lay.addWidget(div)

        # Email
        email_lbl = QLabel("Email Address")
        email_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #374151; background: transparent;")
        body_lay.addWidget(email_lbl)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("you@company.com")
        self.email_input.setFixedHeight(42)
        self.email_input.setStyleSheet("""
            QLineEdit {
                background: #F8FAFC;
                border: 1.5px solid #CBD5E1;
                border-radius: 8px;
                padding: 0 14px;
                font-size: 14px;
                color: #1E293B;
            }
            QLineEdit:focus {
                background: #FFFFFF;
                border-color: #3B82F6;
            }
        """)
        body_lay.addWidget(self.email_input)

        # Password
        pwd_lbl = QLabel("Password")
        pwd_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #374151; background: transparent;")
        body_lay.addWidget(pwd_lbl)

        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setPlaceholderText("Enter your password")
        self.pwd_input.setFixedHeight(42)
        self.pwd_input.setStyleSheet("""
            QLineEdit {
                background: #F8FAFC;
                border: 1.5px solid #CBD5E1;
                border-radius: 8px;
                padding: 0 14px;
                font-size: 14px;
                color: #1E293B;
            }
            QLineEdit:focus {
                background: #FFFFFF;
                border-color: #3B82F6;
            }
        """)
        body_lay.addWidget(self.pwd_input)

        # Show password
        self.show_pwd = QCheckBox("Show password")
        self.show_pwd.setStyleSheet("font-size: 12px; color: #64748B; background: transparent;")
        self.show_pwd.toggled.connect(
            lambda v: self.pwd_input.setEchoMode(
                QLineEdit.EchoMode.Normal if v else QLineEdit.EchoMode.Password
            )
        )
        body_lay.addWidget(self.show_pwd)

        # Error label
        self.error_lbl = QLabel("")
        self.error_lbl.setWordWrap(True)
        self.error_lbl.setVisible(False)
        self.error_lbl.setStyleSheet(
            "color: #EF4444; font-size: 12px; background: #FEF2F2; "
            "border-radius: 6px; padding: 8px 12px;"
        )
        body_lay.addWidget(self.error_lbl)

        # Login button
        self.login_btn = QPushButton("Sign In")
        self.login_btn.setFixedHeight(46)
        self.login_btn.setStyleSheet(f"""
            QPushButton {{
                background: {primary};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-size: 15px;
                font-weight: bold;
            }}
            QPushButton:hover   {{ background: #2563EB; }}
            QPushButton:pressed {{ background: #1D4ED8; }}
            QPushButton:disabled {{ background: #93C5FD; color: #FFFFFF; }}
        """)
        self.login_btn.clicked.connect(self._do_login)
        body_lay.addWidget(self.login_btn)

        footer = QLabel(f"© {cfg.get('company_name', 'SR Manager')}  ·  Secure local authentication")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("font-size: 10px; color: #94A3B8; background: transparent;")
        body_lay.addWidget(footer)

        card_lay.addWidget(body)

        bg_lay.addWidget(card)
        outer.addWidget(bg)

        # Connect Enter key
        self.pwd_input.returnPressed.connect(self._do_login)
        self.email_input.returnPressed.connect(lambda: self.pwd_input.setFocus())

    def _do_login(self):
        email = self.email_input.text().strip()
        pwd   = self.pwd_input.text()
        if not email or not pwd:
            return self._show_error("Please enter your email and password.")
        if not validate_email(email):
            return self._show_error("Please enter a valid email address.")
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

    def _show_error(self, msg: str):
        self.error_lbl.setText(f"⚠  {msg}")
        self.error_lbl.setVisible(True)

    def _set_loading(self, loading: bool):
        self.error_lbl.setVisible(False)
        self.login_btn.setEnabled(not loading)
        self.email_input.setEnabled(not loading)
        self.pwd_input.setEnabled(not loading)
        self.login_btn.setText("Signing in…" if loading else "Sign In")
