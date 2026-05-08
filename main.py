# main.py
"""
SR Manager Enterprise — Entry point.
Initialises PyQt6, runs first-run setup if needed, routes login by role.

Phase 1 fix: dashboard cleanup on logout now cancels QTimers explicitly
before calling deleteLater() to prevent RuntimeError on pending callbacks.
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
from services.backup_service import backup_service

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
        global_config.reload()

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

    # ── Logout — FIXED: stop_polling() now cancels QTimers before deleteLater() ──

    def _on_logout(self):
        # Phase 1 fix: stop_polling() must be called AND we wait for the timer
        # to be fully stopped before scheduling widget destruction.
        # This prevents RuntimeError: wrapped C/C++ object has been deleted
        # when a pending QTimer callback fires after deleteLater().
        for dash in (self._admin_dash, self._mgr_dash, self._tech_dash):
            if dash is not None:
                # stop_polling() calls QTimer.stop() — no more callbacks queued
                dash.stop_polling()

        session.clear()

        # Now safe to remove widgets — no pending timer callbacks remain
        for attr in ("_admin_dash", "_mgr_dash", "_tech_dash"):
            dash = getattr(self, attr)
            if dash is not None:
                self._stack.removeWidget(dash)
                dash.deleteLater()
                setattr(self, attr, None)

        self._login.email_input.clear()
        self._login.pwd_input.clear()
        self._login.error_lbl.setVisible(False)

        QApplication.instance().setStyleSheet(build_stylesheet())
        self._stack.setCurrentWidget(self._login)
        self._update_title()


def main():
    # Pre-startup backup
    backup_service.backup("startup")
    global_config.load()

    app = QApplication(sys.argv)
    app.setApplicationName("SR Manager")
    app.setOrganizationName("SR Manager")
    app.setStyleSheet(build_stylesheet())

    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    # ── Phase 1 fix: First-run setup dialog ──────────────────────────────────
    from db import storage as db_storage
    if db_storage.is_first_run():
        from ui.first_run_setup import FirstRunSetupDialog
        setup = FirstRunSetupDialog()
        result = setup.exec()
        if result != FirstRunSetupDialog.DialogCode.Accepted:
            # User closed the setup dialog — cannot proceed without an admin
            sys.exit(0)
        # Reload config now that setup wrote company/app name
        global_config.reload()
        app.setStyleSheet(build_stylesheet())

    # ── Main window ──────────────────────────────────────────────────────────
    window = MainWindow()
    window.show()

    daily_report_scheduler.start()
    exit_code = app.exec()
    daily_report_scheduler.stop()
    backup_service.backup("shutdown")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
