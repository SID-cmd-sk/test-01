# services/config_service.py
"""
Global configuration — loaded from local data/master_data.json settings/global_config.
Includes branding, WhatsApp, email, labels, and notification settings.

Phase 1 fix: unified read/write path for settings/global_config document.
The special-case bypass in _get_settings_doc() was removed from local_storage_service;
both load() and save() now use storage.get_document / storage.update_document,
which route through the same bucket path.
"""

from __future__ import annotations
import threading
from typing import Dict, Any

DEFAULT_CONFIG: Dict[str, Any] = {
    # Branding
    "app_name":           "SR Manager",
    "company_name":       "SR Manager",
    "primary_color":      "#3B82F6",

    # Label overrides
    "label_sr":           "Service Request",
    "label_open":         "Open",
    "label_in_progress":  "In Progress",
    "label_completed":    "Completed",
    "label_closed":       "Closed",

    # SR Number Pattern
    "sr_number_pattern":  "SR{NNNN}",    # DDMMYYSR{NNNN} or any combo
    "sr_number_suffix":   "",             # appended after generated number
    "sr_number_counter":  "1",            # next counter value
    "sr_types":           "Installation,Activation,Complaint,Service,Maintenance,AMC,Demo,Inspection,Escalation,Purchase Request,Internal Request,Custom",

    # WhatsApp
    "whatsapp_mode":      "qr",
    "whatsapp_number":    "",
    "meta_phone_id":      "",
    "meta_access_token":  "",
    "whatsapp_template":  "{company_name} Daily SR Report\n{report}",
    "report_time":        "09:00",

    # Notifications
    "notify_sr_created":    "true",
    "notify_sr_assigned":   "true",
    "notify_step_done":     "true",
    "notify_sr_closed":     "true",
    "notify_daily_report":  "true",

    # Email
    "smtp_email":         "",
    "smtp_password":      "",
    "email_template":     "{company_name}\n\n{body}",

    # Stats / SLA
    "overdue_days":       "3",

    # System
    "audit_enabled":      "true",

    # Supabase (pre-filled with project credentials)
    "supabase_url":       "https://thkwsemjeqtrumzleeqz.supabase.co",
    "supabase_key":       "sb_publishable_x3p6--QOzt2nwlcNWQsg5A__ngBcoYz",
    "sync_enabled":       "false",   # admin must explicitly enable after running schema
}


class GlobalConfigService:
    def __init__(self):
        self._lock   = threading.Lock()
        self._config = DEFAULT_CONFIG.copy()

    def load(self) -> Dict[str, Any]:
        try:
            from db import storage
            # Phase 1 fix: single code path — both load() and save() use
            # storage.get_document / storage.update_document which go through
            # the same _settings_bucket path. No more dual-path divergence.
            doc = storage.get_document("settings", "global_config")
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

    def get_int(self, key: str, fallback: int = 0) -> int:
        try:
            return int(self.get_val(key, fallback))
        except (ValueError, TypeError):
            return fallback

    def save(self, data: Dict[str, Any]) -> None:
        from db import storage
        merged = DEFAULT_CONFIG.copy()
        for k, v in data.items():
            if k in DEFAULT_CONFIG:
                merged[k] = str(v) if not isinstance(v, bool) else v
        # Phase 1 fix: single write path — creates or updates via the same
        # storage.update_document route that load() reads from.
        try:
            storage.update_document("settings", "global_config", merged)
        except Exception:
            storage.create_document("settings", merged, doc_id="global_config")
        with self._lock:
            self._config = merged

    def label(self, key: str) -> str:
        """Return admin-configured label or a safe default."""
        return str(self.get().get(f"label_{key}", key.replace("_", " ").title()))

    def overdue_days(self) -> int:
        """Phase 1 fix: overdue threshold is now configurable via admin settings."""
        return self.get_int("overdue_days", 3)


global_config = GlobalConfigService()
