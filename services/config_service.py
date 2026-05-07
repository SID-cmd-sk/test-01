# services/config_service.py
"""
Global configuration — loaded from Firestore settings/global_config.
Includes branding, WhatsApp, email, labels, and notification settings.
"""

from __future__ import annotations
import threading
from typing import Dict, Any

DEFAULT_CONFIG: Dict[str, Any] = {
    # Branding
    "app_name":           "SR Manager",
    "company_name":       "SR Manager",
    "primary_color":      "#3B82F6",

    # Label overrides (admin can rename anything)
    "label_sr":           "Service Request",
    "label_open":         "Open",
    "label_in_progress":  "In Progress",
    "label_completed":    "Completed",
    "label_closed":       "Closed",

    # WhatsApp
    "whatsapp_mode":      "qr",          # "qr" | "meta"
    "whatsapp_number":    "",
    "meta_phone_id":      "",
    "meta_access_token":  "",
    "whatsapp_template":  "{company_name} Daily SR Report\n{report}",
    "report_time":        "09:00",

    # Notifications — which events trigger messages
    "notify_sr_created":    "true",
    "notify_sr_assigned":   "true",
    "notify_step_done":     "true",
    "notify_sr_closed":     "true",
    "notify_daily_report":  "true",

    # Email
    "smtp_email":         "",
    "smtp_password":      "",
    "email_template":     "{company_name}\n\n{body}",

    # System
    "audit_enabled":      "true",
}


class GlobalConfigService:
    def __init__(self):
        self._lock   = threading.Lock()
        self._config = DEFAULT_CONFIG.copy()

    def load(self) -> Dict[str, Any]:
        try:
            from firebase_client import firebase
            doc = firebase.get_document("settings", "global_config")
            if doc:
                merged = DEFAULT_CONFIG.copy()
                for k, v in doc.items():
                    if k in DEFAULT_CONFIG:
                        merged[k] = v
                with self._lock:
                    self._config = merged
        except Exception:
            pass
        return self.get()

    def reload(self) -> Dict[str, Any]:
        return self.load()

    def get(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._config)

    def get_val(self, key: str, fallback: Any = "") -> Any:
        return self.get().get(key, fallback)

    def save(self, data: Dict[str, Any]) -> None:
        from firebase_client import firebase
        merged = DEFAULT_CONFIG.copy()
        for k, v in data.items():
            if k in DEFAULT_CONFIG:
                merged[k] = str(v) if not isinstance(v, bool) else v
        try:
            firebase.update_document("settings", "global_config", merged)
        except Exception:
            firebase.create_document("settings", merged, doc_id="global_config")
        with self._lock:
            self._config = merged

    def label(self, key: str) -> str:
        """Return admin-configured label or a safe default."""
        return str(self.get().get(f"label_{key}", key.replace("_", " ").title()))


global_config = GlobalConfigService()
