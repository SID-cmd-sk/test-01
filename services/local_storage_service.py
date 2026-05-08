"""Single-file local JSON storage engine for SR Manager.

All primary records live in ``data/master_data.json``.
This is the sole source of truth — fully offline, no cloud required.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from services.encryption_service import encryption_service

MASTER_DATA_PATH = Path("data/master_data.json")

DEFAULT_MASTER_DATA: Dict[str, Any] = {
    "users": [],
    "tasks": [],
    "sr_entries": [],
    "reports": [],
    "logs": [],
    "settings": {},
    "sync_state": {},
    "archive": {},
}

COLLECTION_MAP = {
    "users": "users",
    "service_requests": "sr_entries",
    "sr_entries": "sr_entries",
    "tasks": "tasks",
    "reports": "reports",
    "audit_log": "logs",
    "logs": "logs",
    "settings": "settings",
    "roles": "settings",
    "role_overrides": "settings",
    "pipeline_templates": "settings",
}

SETTINGS_COLLECTIONS = {"settings", "roles", "role_overrides", "pipeline_templates"}


class LocalStorageError(Exception):
    pass


class TamperDetectionError(LocalStorageError):
    pass


class LocalStorageService:
    """Thread-safe CRUD adapter over the single local master JSON file."""

    def __init__(self, path: str | Path = MASTER_DATA_PATH) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._indexes: Dict[str, Dict[str, dict]] = {}
        self.ensure_exists()

    def ensure_exists(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_payload(copy.deepcopy(DEFAULT_MASTER_DATA))
        else:
            self._ensure_shape()

    def read_all(self) -> Dict[str, Any]:
        with self._lock:
            return self._read_payload()

    def replace_all(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            normalized = self._normalize_master(payload)
            self._write_payload(normalized)
            self._rebuild_indexes(normalized)

    def reset_active_dataset(self, year: int | None = None) -> None:
        with self._lock:
            payload = self._read_payload()
            archive_meta = payload.get("archive", {})
            settings = payload.get("settings", {})
            payload = copy.deepcopy(DEFAULT_MASTER_DATA)
            payload["archive"] = archive_meta
            payload["settings"] = settings
            payload["settings"]["active_year"] = str(year or datetime.now().year)
            self._write_payload(payload)

    def get_collection(self, collection: str) -> List[dict]:
        with self._lock:
            payload = self._read_payload()
            if collection in SETTINGS_COLLECTIONS:
                return self._settings_collection(payload, collection)
            key = self._collection_key(collection)
            return [copy.deepcopy(item) for item in payload.get(key, [])]

    def get_document(self, collection: str, doc_id: str) -> Optional[dict]:
        with self._lock:
            payload = self._read_payload()
            if collection in SETTINGS_COLLECTIONS:
                return copy.deepcopy(self._get_settings_doc(payload, collection, doc_id))
            key = self._collection_key(collection)
            for item in payload.get(key, []):
                if self._doc_id(item) == doc_id:
                    return copy.deepcopy(item)
            return None

    def create_document(self, collection: str, data: dict, doc_id: Optional[str] = None) -> dict:
        with self._lock:
            payload = self._read_payload()
            doc = copy.deepcopy(data)
            doc_id = doc_id or doc.get("id") or doc.get("uid") or str(uuid.uuid4())
            doc.setdefault("id", doc_id)
            doc.setdefault("created_at", self._now())
            doc["updated_at"] = doc.get("updated_at") or doc["created_at"]
            doc["_dirty"] = True
            doc["_deleted"] = False

            if collection in SETTINGS_COLLECTIONS:
                self._set_settings_doc(payload, collection, doc_id, doc)
            else:
                key = self._collection_key(collection)
                payload.setdefault(key, [])
                if any(self._doc_id(item) == doc_id for item in payload[key]):
                    raise LocalStorageError(f"Document already exists: {collection}/{doc_id}")
                payload[key].append(doc)
            self._write_payload(payload)
            return copy.deepcopy(doc)

    def upsert_document(self, collection: str, data: dict, doc_id: Optional[str] = None) -> dict:
        existing_id = doc_id or data.get("id") or data.get("uid")
        if existing_id and self.get_document(collection, str(existing_id)):
            self.update_document(collection, str(existing_id), data)
            return self.get_document(collection, str(existing_id)) or data
        return self.create_document(collection, data, doc_id=existing_id)

    def update_document(self, collection: str, doc_id: str, data: dict) -> None:
        with self._lock:
            payload = self._read_payload()
            updates = copy.deepcopy(data)
            updates["updated_at"] = updates.get("updated_at") or self._now()
            updates["_dirty"] = True
            if collection in SETTINGS_COLLECTIONS:
                current = self._get_settings_doc(payload, collection, doc_id) or {"id": doc_id}
                current.update(updates)
                self._set_settings_doc(payload, collection, doc_id, current)
            else:
                key = self._collection_key(collection)
                for item in payload.get(key, []):
                    if self._doc_id(item) == doc_id:
                        item.update(updates)
                        self._write_payload(payload)
                        return
                raise LocalStorageError(f"Document not found: {collection}/{doc_id}")
            self._write_payload(payload)

    def delete_document(self, collection: str, doc_id: str) -> None:
        with self._lock:
            payload = self._read_payload()
            if collection in SETTINGS_COLLECTIONS:
                bucket = self._settings_bucket(payload, collection)
                bucket.pop(doc_id, None)
            else:
                key = self._collection_key(collection)
                payload[key] = [item for item in payload.get(key, []) if self._doc_id(item) != doc_id]
            self._write_payload(payload)

    def query_collection(self, collection: str, field: str, op: str, value: Any) -> List[dict]:
        items = self.get_collection(collection)
        op = op.upper()
        result = []
        for item in items:
            current = item.get(field)
            if op in ("EQUAL", "EQ", "==") and current == value:
                result.append(item)
            elif op in ("NOT_EQUAL", "NE", "!=") and current != value:
                result.append(item)
            elif op in ("GREATER_THAN", ">") and current > value:
                result.append(item)
            elif op in ("LESS_THAN", "<") and current < value:
                result.append(item)
        return result

    def mark_clean(self, collection: str, ids: Iterable[str]) -> None:
        with self._lock:
            payload = self._read_payload()
            id_set = set(ids)
            key = self._collection_key(collection)
            for item in payload.get(key, []):
                if self._doc_id(item) in id_set:
                    item["_dirty"] = False
            self._write_payload(payload)

    def changed_records(self) -> Dict[str, List[dict]]:
        payload = self.read_all()
        return {
            "users": [i for i in payload["users"] if i.get("_dirty")],
            "service_requests": [i for i in payload["sr_entries"] if i.get("_dirty")],
            "tasks": [i for i in payload["tasks"] if i.get("_dirty")],
            "reports": [i for i in payload["reports"] if i.get("_dirty")],
            "logs": [i for i in payload["logs"] if i.get("_dirty")],
        }

    def append_log(self, action: str, details: str = "", target_id: str = "", actor: dict | None = None) -> dict:
        entry = {
            "id": str(uuid.uuid4()),
            "action": action,
            "details": details,
            "target_id": target_id,
            "actor_uid": (actor or {}).get("uid", ""),
            "actor_name": (actor or {}).get("name", ""),
            "actor_role": (actor or {}).get("role", ""),
            "timestamp": self._now(),
            "_dirty": True,
        }
        return self.create_document("logs", entry, doc_id=entry["id"])

    def _read_payload(self) -> Dict[str, Any]:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        payload = raw.get("data", raw)
        meta = raw.get("_meta")
        payload = self._normalize_master(payload)
        if meta and not encryption_service.validate_signature(payload, meta.get("signature", "")):
            payload.setdefault("sync_state", {})["tamper_warning"] = "Local data signature validation failed; data loaded in recovery mode."
        return payload

    def _write_payload(self, payload: Dict[str, Any]) -> None:
        payload = self._normalize_master(payload)
        envelope = {"_meta": encryption_service.build_meta(payload), "data": payload}
        fd, tmp_name = tempfile.mkstemp(prefix="master_data_", suffix=".json", dir=str(self.path.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(envelope, fh, indent=2, ensure_ascii=False)
        os.replace(tmp_name, self.path)

    def _ensure_shape(self) -> None:
        payload = self._read_payload()
        self._write_payload(payload)

    def _normalize_master(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        normalized = copy.deepcopy(DEFAULT_MASTER_DATA)
        for key in normalized:
            if key in payload and isinstance(payload[key], type(normalized[key])):
                normalized[key] = payload[key]
        return normalized

    def _collection_key(self, collection: str) -> str:
        if collection not in COLLECTION_MAP:
            return collection
        return COLLECTION_MAP[collection]

    def _settings_bucket(self, payload: Dict[str, Any], collection: str) -> Dict[str, Any]:
        settings = payload.setdefault("settings", {})
        if collection == "settings":
            return settings.setdefault("documents", {})
        return settings.setdefault(collection, {})

    def _settings_collection(self, payload: Dict[str, Any], collection: str) -> List[dict]:
        bucket = self._settings_bucket(payload, collection)
        return [copy.deepcopy({**v, "id": k}) if isinstance(v, dict) else {"id": k, "value": v}
                for k, v in bucket.items()]

    def _get_settings_doc(self, payload: Dict[str, Any], collection: str, doc_id: str) -> Optional[dict]:
        bucket = self._settings_bucket(payload, collection)
        doc = bucket.get(doc_id)
        if isinstance(doc, dict):
            return {**doc, "id": doc.get("id", doc_id)}
        if doc is not None:
            return {"id": doc_id, "value": doc}
        if collection == "settings" and doc_id == "global_config":
            return payload.get("settings", {}).get("global_config")
        return None

    def _set_settings_doc(self, payload: Dict[str, Any], collection: str, doc_id: str, doc: dict) -> None:
        bucket = self._settings_bucket(payload, collection)
        bucket[doc_id] = copy.deepcopy(doc)
        if collection == "settings" and doc_id == "global_config":
            payload.setdefault("settings", {})["global_config"] = copy.deepcopy(doc)

    def _doc_id(self, item: dict) -> str:
        return str(item.get("id") or item.get("uid") or "")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _rebuild_indexes(self, payload: Dict[str, Any]) -> None:
        self._indexes = {
            key: {self._doc_id(item): item for item in payload.get(key, [])}
            for key in ("users", "sr_entries", "tasks", "reports", "logs")
        }


local_storage = LocalStorageService()
