# services/notification_service.py
"""
Desktop Notification Service.

Shows system tray / desktop notifications for SR events.
Works on Windows via QSystemTrayIcon. Falls back to a non-blocking
in-app toast if the tray icon is not available.

Usage:
    from services.notification_service import notify
    notify("SR Assigned", "SR #1042 has been assigned to you.", level="info")
"""

from __future__ import annotations

import threading
from typing import Literal


Level = Literal["info", "warning", "error", "success"]

_tray_icon = None   # set by main window after app starts


def set_tray_icon(icon) -> None:
    """Register the QSystemTrayIcon instance from the main window."""
    global _tray_icon
    _tray_icon = icon


def notify(
    title: str,
    message: str,
    level: Level = "info",
    duration_ms: int = 5000,
) -> None:
    """
    Show a desktop notification. Always non-blocking — runs in a daemon thread.

    Args:
        title:       Notification headline (e.g. "SR Assigned")
        message:     Body text (e.g. "SR #1042 assigned to Rahul Singh")
        level:       "info" | "warning" | "error" | "success"
        duration_ms: How long the notification stays visible (ms)
    """
    def _show():
        try:
            _show_qt(title, message, level, duration_ms)
        except Exception:
            pass   # never crash the app over a notification

    threading.Thread(target=_show, daemon=True).start()


def _show_qt(title: str, message: str, level: Level, duration_ms: int) -> None:
    """Attempt Qt system tray notification, fall back to QMessageBox-style popup."""
    try:
        from PyQt6.QtWidgets import QSystemTrayIcon, QApplication
        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG

        icon_map = {
            "info":    QSystemTrayIcon.MessageIcon.Information,
            "warning": QSystemTrayIcon.MessageIcon.Warning,
            "error":   QSystemTrayIcon.MessageIcon.Critical,
            "success": QSystemTrayIcon.MessageIcon.Information,
        }
        qt_icon = icon_map.get(level, QSystemTrayIcon.MessageIcon.Information)

        if _tray_icon is not None and _tray_icon.isVisible():
            # Main thread dispatch required for Qt widgets
            def _do():
                _tray_icon.showMessage(title, message, qt_icon, duration_ms)
            app = QApplication.instance()
            if app:
                # Schedule on main thread
                QMetaObject.invokeMethod(
                    app, "processEvents",
                    Qt.ConnectionType.QueuedConnection
                )
                _do()
        # If no tray icon, silently succeed (audit log captures events anyway)
    except Exception:
        pass


def notify_sr_event(event: str, sr: dict, assignee_name: str = "") -> None:
    """
    Convenience wrapper for SR lifecycle events.
    Composes the notification from the event type and SR metadata.
    """
    from services.config_service import global_config
    cfg     = global_config.get()
    company = cfg.get("company_name", "SR Manager")
    title_  = sr.get("title", "Service Request")

    messages = {
        "sr_created":  (f"New SR Created", f"'{title_}' has been logged.", "info"),
        "sr_assigned": (f"SR Assigned to You", f"'{title_}' is now assigned to {assignee_name or 'you'}.", "info"),
        "step_done":   (f"Pipeline Step Completed", f"A step was completed on '{title_}'.", "success"),
        "sr_closed":   (f"SR Closed", f"'{title_}' has been closed.", "success"),
        "sr_overdue":  (f"SR Overdue", f"'{title_}' is past its SLA deadline.", "warning"),
        "sr_escalated":(f"SR Escalated", f"'{title_}' has been escalated.", "error"),
    }

    title_str, msg_str, level = messages.get(
        event, (f"SR Update — {company}", f"'{title_}' was updated.", "info")
    )
    notify(title_str, msg_str, level)


# ── In-memory notification queue (for in-app notification bell) ───────────────

_notification_queue: list = []
_queue_lock = threading.Lock()
_MAX_QUEUE = 50


def push_in_app(title: str, message: str, level: Level = "info") -> None:
    """
    Store a notification in the in-app queue (for the notification bell icon).
    The admin/manager dashboard can poll this queue to update the badge count.
    """
    from utils.helpers import utc_now_iso
    with _queue_lock:
        _notification_queue.append({
            "title":     title,
            "message":   message,
            "level":     level,
            "timestamp": utc_now_iso(),
            "read":      False,
        })
        # Keep queue bounded
        if len(_notification_queue) > _MAX_QUEUE:
            _notification_queue.pop(0)


def get_unread_count() -> int:
    with _queue_lock:
        return sum(1 for n in _notification_queue if not n["read"])


def get_all_notifications() -> list:
    with _queue_lock:
        return list(reversed(_notification_queue))


def mark_all_read() -> None:
    with _queue_lock:
        for n in _notification_queue:
            n["read"] = True


def clear_notifications() -> None:
    with _queue_lock:
        _notification_queue.clear()
