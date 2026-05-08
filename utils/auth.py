# utils/auth.py
"""
Session management + dynamic permission system.
Permissions are loaded from local roles collection at login.
"""

from typing import Optional, List, Dict, Any

# ── Default permission sets per built-in role ─────────────────────────────────
DEFAULT_PERMISSIONS: Dict[str, List[str]] = {
    "admin": [
        "view_all_srs", "create_sr", "close_sr", "assign_sr",
        "create_user", "edit_user", "delete_user", "manage_roles",
        "view_reports", "view_all_reports", "manage_settings",
        "build_pipelines", "skip_pipeline_steps", "view_audit_log",
        "export_data", "manage_notifications", "manage_branding",
        "danger_zone",
    ],
    "manager": [
        "view_all_srs", "create_sr", "close_sr", "assign_sr",
        "view_reports",
    ],
    "technical": [
        "view_own_srs", "create_sr", "update_sr_status",
        "skip_pipeline_steps", "view_reports",
    ],
}


class Session:
    """Holds logged-in user state and resolved permissions."""

    _instance: Optional["Session"] = None

    def __init__(self):
        self.uid:         Optional[str]       = None
        self.email:       Optional[str]       = None
        self.name:        Optional[str]       = None
        self.role:        Optional[str]       = None
        self.whatsapp:    Optional[str]       = None
        self.permissions: List[str]           = []
        self.role_doc:    Optional[Dict]      = None   # full role document

    @classmethod
    def get(cls) -> "Session":
        if cls._instance is None:
            cls._instance = Session()
        return cls._instance

    def set(self, uid: str, email: str, name: str, role: str,
            whatsapp: str = "", permissions: Optional[List[str]] = None,
            role_doc: Optional[Dict] = None):
        self.uid         = uid
        self.email       = email
        self.name        = name
        self.role        = role
        self.whatsapp    = whatsapp
        self.permissions = permissions or DEFAULT_PERMISSIONS.get(role, [])
        self.role_doc    = role_doc

    def clear(self):
        self.uid = self.email = self.name = self.role = self.whatsapp = self.role_doc = None
        self.permissions = []

    def has(self, permission: str) -> bool:
        return permission in self.permissions

    # ── Convenience shortcuts ──────────────────────────────────────────────────
    def is_logged_in(self)  -> bool: return self.uid is not None
    def is_admin(self)      -> bool: return self.role == "admin"
    def is_manager(self)    -> bool: return self.role == "manager"
    def is_technical(self)  -> bool: return self.role == "technical"

    def can(self, perm: str) -> bool:
        return self.has(perm)


# Global singleton
session = Session.get()
