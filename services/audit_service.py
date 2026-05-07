# services/audit_service.py
"""
Audit log — writes every significant action to Firestore audit_log collection.
Non-blocking: fire and forget via background thread.
"""

import threading
from utils.helpers import utc_now_iso


def log_action(action: str, details: str = "", target_id: str = "") -> None:
    """
    Write an audit entry asynchronously.
    Never raises — silently swallows errors.
    """
    def _write():
        try:
            from firebase_client import firebase
            from utils.auth import session
            from services.config_service import global_config

            if global_config.get_val("audit_enabled") != "true":
                return

            firebase.create_document("audit_log", {
                "actor_uid":   session.uid or "",
                "actor_name":  session.name or "",
                "actor_role":  session.role or "",
                "action":      action,
                "details":     details,
                "target_id":   target_id,
                "timestamp":   utc_now_iso(),
            })
        except Exception:
            pass

    threading.Thread(target=_write, daemon=True).start()
