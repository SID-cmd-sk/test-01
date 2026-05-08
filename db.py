# db.py
"""Offline local storage client for SR Manager.

All data is stored in ``data/master_data.json``.
No internet connection or cloud service is required for local operations.
Supabase sync is handled by services/supabase_service.py.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.encryption_service import encryption_service
from services.local_storage_service import local_storage


class LocalAuthError(Exception):
    pass


class LocalNetworkError(Exception):
    pass


# Legacy aliases
FirebaseAuthError    = LocalAuthError
FirebaseNetworkError = LocalNetworkError


class LocalStorageClient:
    """Offline CRUD client backed by the local JSON store."""

    def __init__(self) -> None:
        self._uid: Optional[str] = None
        self._lock = threading.Lock()
        # Bootstrap admin is NO LONGER created here.
        # It is created by ui/first_run_setup.py on first launch.
        # This prevents personal credentials from being baked into source code.

    @property
    def uid(self) -> Optional[str]:
        return self._uid

    # ── Auth ──────────────────────────────────────────────────────────────────

    def login(self, email: str, password: str) -> Dict:
        user = self._find_user_by_email(email)
        if not user or not user.get("active", True):
            raise LocalAuthError("Invalid email or password.")
        stored_hash = user.get("password_hash", "")
        if stored_hash:
            if not encryption_service.verify_password(password, stored_hash):
                raise LocalAuthError("Invalid email or password.")
        elif password != user.get("password", ""):
            raise LocalAuthError("Invalid email or password.")
        with self._lock:
            self._uid = str(user.get("uid") or user.get("id"))
        return {"uid": self._uid, "email": user.get("email", email)}

    def logout(self) -> None:
        with self._lock:
            self._uid = None

    def create_user(self, email: str, password: str) -> str:
        self._require_if_protected("users", "create")
        if self._find_user_by_email(email):
            raise LocalAuthError("An account with this email already exists.")
        uid = str(uuid.uuid4())
        pending = local_storage.read_all()
        pending.setdefault("sync_state", {})[f"password_hash:{uid}"] = \
            encryption_service.hash_password(password)
        local_storage.replace_all(pending)
        return uid

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def get_document(self, collection: str, doc_id: str) -> Optional[dict]:
        return self._strip_private(local_storage.get_document(collection, doc_id))

    def get_collection(self, collection: str) -> List[dict]:
        return [self._strip_private(doc) for doc in local_storage.get_collection(collection)]

    def create_document(self, collection: str, data: dict,
                        doc_id: Optional[str] = None) -> dict:
        self._require_if_protected(collection, "create")
        prepared = dict(data)
        if collection == "users":
            uid = doc_id or prepared.get("uid") or prepared.get("id")
            pending_key = f"password_hash:{uid}"
            payload = local_storage.read_all()
            password_hash = payload.setdefault("sync_state", {}).pop(pending_key, None)
            if password_hash:
                prepared["password_hash"] = password_hash
                local_storage.replace_all(payload)
        return self._strip_private(
            local_storage.create_document(collection, prepared, doc_id=doc_id)
        )

    def update_document(self, collection: str, doc_id: str, data: dict) -> None:
        self._require_if_protected(collection, "update")
        prepared = dict(data)
        if collection == "users":
            # Guard: master admin attributes are immutable
            existing = local_storage.get_document(collection, doc_id)
            if existing and existing.get("is_master_admin"):
                prepared.pop("is_master_admin", None)   # immutable flag
                prepared.pop("active", None)             # cannot be deactivated
                if prepared.get("role") and prepared["role"] != "admin":
                    prepared.pop("role", None)           # must stay admin
            if "password" in prepared:
                prepared["password_hash"] = encryption_service.hash_password(
                    str(prepared.pop("password"))
                )
        local_storage.update_document(collection, doc_id, prepared)

    def delete_document(self, collection: str, doc_id: str) -> None:
        self._require_if_protected(collection, "delete")
        if collection == "users":
            doc = local_storage.get_document(collection, doc_id)
            if doc and doc.get("is_master_admin"):
                raise LocalAuthError("The master admin account cannot be deleted.")
        local_storage.delete_document(collection, doc_id)

    def query_collection(self, collection: str, field: str,
                         op: str, value: Any) -> List[dict]:
        return [
            self._strip_private(doc)
            for doc in local_storage.query_collection(collection, field, op, value)
        ]

    # ── Convenience helpers ───────────────────────────────────────────────────

    def update_status(self, sr_id: str, status: str) -> None:
        self.update_document("service_requests", sr_id, {
            "status":     status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    def get_my_srs(self, uid: str) -> List[dict]:
        return [
            sr for sr in self.get_collection("service_requests")
            if sr.get("assigned_to") == uid or sr.get("created_by") == uid
        ]

    def is_first_run(self) -> bool:
        """True when no users exist — first-run setup dialog should be shown."""
        return len(local_storage.get_collection("users")) == 0

    # ── Internal ──────────────────────────────────────────────────────────────

    def _require_if_protected(self, collection: str, action: str) -> None:
        from utils.auth import permission_for, require_permission, session
        perm = permission_for(collection, action)
        # First-run setup runs before a session exists and only when no local users exist.
        if perm and (session.is_logged_in() or local_storage.get_collection("users")):
            require_permission(perm)

    def _find_user_by_email(self, email: str) -> Optional[dict]:
        email_lower = email.strip().lower()
        for user in local_storage.get_collection("users"):
            if str(user.get("email", "")).strip().lower() == email_lower:
                return user
        return None

    def _strip_private(self, doc: Optional[dict]) -> Optional[dict]:
        if doc is None:
            return None
        safe = dict(doc)
        safe.pop("password_hash", None)
        safe.pop("password", None)
        return safe


# ── Singleton ─────────────────────────────────────────────────────────────────
storage = LocalStorageClient()

# Legacy alias — keeps any code that still references `firebase` working
firebase = storage
