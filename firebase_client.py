# firebase_client.py
"""Local-first compatibility client.

Existing UI code imports ``firebase`` and Firebase-style exceptions.  This module
keeps that API stable while redirecting primary storage to the single local JSON
store at ``data/master_data.json``.  Supabase sync is handled separately by
``services.sync_service`` and is never primary storage.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.encryption_service import encryption_service
from services.local_storage_service import local_storage


class FirebaseAuthError(Exception):
    pass


class FirebaseNetworkError(Exception):
    pass


class FirebaseClient:
    """Drop-in local adapter for the former Firebase REST client."""

    def __init__(self) -> None:
        self._uid: Optional[str] = None
        self._lock = threading.Lock()
        self._ensure_bootstrap_admin()

    @property
    def uid(self) -> Optional[str]:
        return self._uid

    def login(self, email: str, password: str) -> Dict:
        user = self._find_user_by_email(email)
        if not user or not user.get("active", True):
            raise FirebaseAuthError("Invalid email or password.")
        stored_hash = user.get("password_hash", "")
        if stored_hash:
            if not encryption_service.verify_password(password, stored_hash):
                raise FirebaseAuthError("Invalid email or password.")
        elif password != user.get("password", ""):
            raise FirebaseAuthError("Invalid email or password.")
        with self._lock:
            self._uid = str(user.get("uid") or user.get("id"))
        return {"uid": self._uid, "email": user.get("email", email)}

    def logout(self) -> None:
        with self._lock:
            self._uid = None

    def create_user(self, email: str, password: str) -> str:
        if self._find_user_by_email(email):
            raise FirebaseAuthError("An account with this email already exists.")
        uid = str(uuid.uuid4())
        pending = local_storage.read_all()
        pending.setdefault("sync_state", {})[f"password_hash:{uid}"] = encryption_service.hash_password(password)
        local_storage.replace_all(pending)
        return uid

    def get_document(self, collection: str, doc_id: str) -> Optional[dict]:
        return self._strip_private(local_storage.get_document(collection, doc_id))

    def get_collection(self, collection: str) -> List[dict]:
        return [self._strip_private(doc) for doc in local_storage.get_collection(collection)]

    def create_document(self, collection: str, data: dict, doc_id: Optional[str] = None) -> dict:
        prepared = dict(data)
        if collection == "users":
            uid = doc_id or prepared.get("uid") or prepared.get("id")
            pending_key = f"password_hash:{uid}"
            payload = local_storage.read_all()
            password_hash = payload.setdefault("sync_state", {}).pop(pending_key, None)
            if password_hash:
                prepared["password_hash"] = password_hash
                local_storage.replace_all(payload)
        return self._strip_private(local_storage.create_document(collection, prepared, doc_id=doc_id))

    def update_document(self, collection: str, doc_id: str, data: dict) -> None:
        prepared = dict(data)
        if collection == "users" and "password" in prepared:
            prepared["password_hash"] = encryption_service.hash_password(str(prepared.pop("password")))
        local_storage.update_document(collection, doc_id, prepared)

    def delete_document(self, collection: str, doc_id: str) -> None:
        local_storage.delete_document(collection, doc_id)

    def query_collection(self, collection: str, field: str, op: str, value: Any) -> List[dict]:
        return [self._strip_private(doc) for doc in local_storage.query_collection(collection, field, op, value)]

    def update_status(self, sr_id: str, status: str) -> None:
        self.update_document("service_requests", sr_id, {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    def get_my_srs(self, uid: str) -> List[dict]:
        return [sr for sr in self.get_collection("service_requests")
                if sr.get("assigned_to") == uid or sr.get("created_by") == uid]

    def _find_user_by_email(self, email: str) -> Optional[dict]:
        email_lower = email.strip().lower()
        for user in local_storage.get_collection("users"):
            if str(user.get("email", "")).strip().lower() == email_lower:
                return user
        return None

    def _ensure_bootstrap_admin(self) -> None:
        if local_storage.get_collection("users"):
            return
        uid = "local-admin"
        local_storage.create_document("users", {
            "uid": uid,
            "email": "admin@local",
            "name": "Local Administrator",
            "role": "admin",
            "whatsapp_number": "",
            "active": True,
            "password_hash": encryption_service.hash_password("admin123"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }, doc_id=uid)

    def _strip_private(self, doc: Optional[dict]) -> Optional[dict]:
        if doc is None:
            return None
        safe = dict(doc)
        safe.pop("password_hash", None)
        safe.pop("password", None)
        return safe


firebase = FirebaseClient()
