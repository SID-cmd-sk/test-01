"""Local audit logging.

Audit entries are appended to ``data/master_data.json`` under the single ``logs``
array.  The sync engine may later bridge these entries, but local storage remains
the source of truth and the function never blocks UI threads.
"""

import threading

from services.local_storage_service import local_storage


def log_action(action: str, details: str = "", target_id: str = "") -> None:
    """Write an audit entry asynchronously and never raise into the UI."""
    def _write():
        try:
            from utils.auth import session
            from services.config_service import global_config

            if global_config.get_val("audit_enabled") != "true":
                return

            local_storage.append_log(
                action,
                details,
                target_id,
                actor={
                    "uid": session.uid or "",
                    "name": session.name or "",
                    "role": session.role or "",
                },
            )
        except Exception:
            pass

    threading.Thread(target=_write, daemon=True).start()
