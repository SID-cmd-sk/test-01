# main.py
"""
SR Manager v2 — Entry point.
Initialises PyQt6, applies dynamic stylesheet, routes login by role.
"""

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSlot

from utils.auth import session
from utils.helpers import build_stylesheet
from services.config_service import global_config
from services.scheduler import daily_report_scheduler

from ui.login import LoginScreen
from ui.admin_dashboard import AdminDashboard
from ui.manager_dashboard import ManagerDashboard
from ui.technical_dashboard import TechnicalDashboard


class MainWindow(QMainWindow):
    """Root window — stacked widget: Login ↔ role dashboards."""

    def __init__(self):
        super().__init__()
        self._update_title()
        self.setMinimumSize(1100, 700)
        self.resize(1320, 840)
        self._center()

        self._stack      = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._login      = LoginScreen()
        self._admin_dash: AdminDashboard    | None = None
        self._mgr_dash:   ManagerDashboard  | None = None
        self._tech_dash:  TechnicalDashboard| None = None

        self._stack.addWidget(self._login)
        self._login.login_success.connect(self._on_login)

    def _center(self):
        screen = QApplication.primaryScreen()
        if screen:
            g = screen.availableGeometry()
            self.move((g.width() - self.width()) // 2,
                      (g.height() - self.height()) // 2)

    def _update_title(self):
        cfg  = global_config.get()
        name = cfg.get("app_name", "SR Manager")
        self.setWindowTitle(name)

    # ── Login routing ──────────────────────────────────────────────────────────

    @pyqtSlot(str, str, str, str)
    def _on_login(self, uid: str, email: str, name: str, role: str):
        # Reload config now that Firebase token is live
        global_config.reload()

        # Apply primary colour from settings
        cfg   = global_config.get()
        style = build_stylesheet(cfg.get("primary_color", "#3B82F6"))
        QApplication.instance().setStyleSheet(style)

        self._update_title()

        if role == "admin":
            self._show_admin()
        elif role == "manager":
            self._show_manager()
        elif role == "technical":
            self._show_technical()
        else:
            # Custom / unknown role — try technical dashboard as fallback
            QMessageBox.information(
                self, "Role Info",
                f"Logged in with role '{role}'.\n"
                f"Using Technical dashboard as default.\n"
                f"Contact your admin to assign a recognised role."
            )
            self._show_technical()

    # ── Dashboard display ──────────────────────────────────────────────────────

    def _show_admin(self):
        if self._admin_dash is None:
            self._admin_dash = AdminDashboard()
            self._admin_dash.logout_requested.connect(self._on_logout)
            self._stack.addWidget(self._admin_dash)
        self._stack.setCurrentWidget(self._admin_dash)
        cfg = global_config.get()
        self.setWindowTitle(
            f"{cfg.get('app_name','SR Manager')} — Admin Portal ({session.name})"
        )
        self._admin_dash.start_polling()

    def _show_manager(self):
        if self._mgr_dash is None:
            self._mgr_dash = ManagerDashboard()
            self._mgr_dash.logout_requested.connect(self._on_logout)
            self._stack.addWidget(self._mgr_dash)
        self._stack.setCurrentWidget(self._mgr_dash)
        cfg = global_config.get()
        self.setWindowTitle(
            f"{cfg.get('app_name','SR Manager')} — Manager Portal ({session.name})"
        )
        self._mgr_dash.start_polling()

    def _show_technical(self):
        if self._tech_dash is None:
            self._tech_dash = TechnicalDashboard()
            self._tech_dash.logout_requested.connect(self._on_logout)
            self._stack.addWidget(self._tech_dash)
        self._stack.setCurrentWidget(self._tech_dash)
        cfg = global_config.get()
        self.setWindowTitle(
            f"{cfg.get('app_name','SR Manager')} — Field Portal ({session.name})"
        )
        self._tech_dash.start_polling()

    # ── Logout ─────────────────────────────────────────────────────────────────

    def _on_logout(self):
        for dash in (self._admin_dash, self._mgr_dash, self._tech_dash):
            if dash:
                dash.stop_polling()

        session.clear()

        for attr in ("_admin_dash", "_mgr_dash", "_tech_dash"):
            dash = getattr(self, attr)
            if dash:
                self._stack.removeWidget(dash)
                dash.deleteLater()
                setattr(self, attr, None)

        self._login.email_input.clear()
        self._login.pwd_input.clear()
        self._login.error_lbl.setVisible(False)

        # Reset stylesheet to default on logout
        QApplication.instance().setStyleSheet(build_stylesheet())
        self._stack.setCurrentWidget(self._login)
        self._update_title()


def main():
    # Load config with defaults before window appears
    global_config.load()

    app = QApplication(sys.argv)
    app.setApplicationName("SR Manager")
    app.setOrganizationName("SR Manager")

    # Apply default stylesheet (will be overridden after login with saved color)
    app.setStyleSheet(build_stylesheet())

    # HiDPI
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    window = MainWindow()
    window.show()

    daily_report_scheduler.start()
    exit_code = app.exec()
    daily_report_scheduler.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
