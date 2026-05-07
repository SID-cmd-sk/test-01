# ui/login.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from firebase_client import firebase, FirebaseAuthError, FirebaseNetworkError
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
            auth     = firebase.login(self.email, self.password)
            user_doc = firebase.get_document("users", auth["uid"])
            if not user_doc:
                self.error.emit(
                    "Your account exists but is not in the database.\n"
                    "Contact your administrator.")
                return

            # Load custom role permissions if available
            role = user_doc.get("role", "technical")
            try:
                role_doc = firebase.get_document("role_overrides", role) or \
                           firebase.get_document("roles", role)
            except Exception:
                role_doc = None
            user_doc["_role_doc"] = role_doc
            self.success.emit(auth, user_doc)
        except (FirebaseAuthError, FirebaseNetworkError) as e:
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
        card_lay.setSpacing(16)
        card_lay.setContentsMargins(40, 40, 40, 40)

        icon = QLabel("🛠"); icon.setStyleSheet("font-size: 40px;"); icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ttl  = QLabel(cfg.get("app_name", "SR Manager")); ttl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ttl.setStyleSheet("font-size: 24px; font-weight: bold; color: #0F172A;")
        sub  = QLabel(cfg.get("company_name", "Service Request Management"))
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("font-size: 12px; color: #64748B;")

        for w in (icon, ttl, sub):
            card_lay.addWidget(w)

        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine); div.setStyleSheet("color: #E2E8F0;")
        card_lay.addWidget(div)

        card_lay.addWidget(self._lbl("Email Address"))
        self.email_input = QLineEdit(); self.email_input.setPlaceholderText("you@company.com"); self.email_input.setFixedHeight(40)
        card_lay.addWidget(self.email_input)

        card_lay.addWidget(self._lbl("Password"))
        self.pwd_input = QLineEdit(); self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setPlaceholderText("••••••••"); self.pwd_input.setFixedHeight(40)
        card_lay.addWidget(self.pwd_input)

        self.error_lbl = QLabel(""); self.error_lbl.setObjectName("error_label")
        self.error_lbl.setWordWrap(True); self.error_lbl.setVisible(False)
        card_lay.addWidget(self.error_lbl)

        self.login_btn = QPushButton("Sign In"); self.login_btn.setObjectName("btn_primary")
        self.login_btn.setFixedHeight(42); self.login_btn.clicked.connect(self._do_login)
        card_lay.addWidget(self.login_btn)

        self.pwd_input.returnPressed.connect(self._do_login)
        self.email_input.returnPressed.connect(lambda: self.pwd_input.setFocus())

        footer = QLabel(f"© {cfg.get('company_name', 'SR Manager')}  •  All roles require admin setup")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("font-size: 10px; color: #94A3B8;")
        card_lay.addWidget(footer)

        bg_lay.addWidget(card)
        outer.addWidget(bg)

    @staticmethod
    def _lbl(text: str) -> QLabel:
        l = QLabel(text); l.setStyleSheet("font-size: 12px; font-weight: 600; color: #374151;")
        return l

    def _do_login(self):
        email = self.email_input.text().strip()
        pwd   = self.pwd_input.text()
        if not email or not pwd:
            self._show_error("Please enter your email and password."); return
        if not validate_email(email):
            self._show_error("Please enter a valid email address."); return
        self._set_loading(True)
        self._worker = LoginWorker(email, pwd)
        self._worker.success.connect(self._on_success)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    @pyqtSlot(dict, dict)
    def _on_success(self, auth: dict, user_doc: dict):
        self._set_loading(False)
        # Apply custom role permissions to session
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
        self._set_loading(False); self._show_error(msg)

    def _show_error(self, msg: str):
        self.error_lbl.setText(f"⚠ {msg}"); self.error_lbl.setVisible(True)

    def _set_loading(self, loading: bool):
        self.error_lbl.setVisible(False)
        self.login_btn.setEnabled(not loading)
        self.email_input.setEnabled(not loading)
        self.pwd_input.setEnabled(not loading)
        self.login_btn.setText("Signing in…" if loading else "Sign In")
