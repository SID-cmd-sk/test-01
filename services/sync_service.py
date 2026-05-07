"""Supabase bridge sync engine.

Supabase is used only as a temporary exchange bridge.  The local
``data/master_data.json`` file remains the source of truth, and successfully
transferred bridge rows are deleted from Supabase after import.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from services.backup_service import backup_service
from services.local_storage_service import local_storage

SUPABASE_URL = "https://thkwsemjeqtrumzleeqz.supabase.co"
SUPABASE_KEY_PLACEHOLDER = "USE_EXISTING_PUBLISHABLE_KEY_FROM_PROJECT"
BRIDGE_TABLE = "sync_bridge"
ENV_PATH = Path(".env")


class SyncService:
    """Threaded, retryable, changed-record-only sync service."""

    def __init__(self, interval_seconds: int = 300) -> None:
        self.interval_seconds = interval_seconds
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._syncing = False
        self.env = self.ensure_env()

    def ensure_env(self) -> Dict[str, str]:
        """Create and load .env if missing, without committing secret material."""
        if not ENV_PATH.exists():
            ENV_PATH.write_text(
                f"SUPABASE_URL={SUPABASE_URL}\n"
                f"SUPABASE_KEY={SUPABASE_KEY_PLACEHOLDER}\n",
                encoding="utf-8",
            )
        if importlib.util.find_spec("dotenv") is not None:
            dotenv = importlib.import_module("dotenv")
            dotenv.load_dotenv(ENV_PATH)
        return {
            "SUPABASE_URL": os.environ.get("SUPABASE_URL", SUPABASE_URL),
            "SUPABASE_KEY": os.environ.get("SUPABASE_KEY", SUPABASE_KEY_PLACEHOLDER),
        }

    def start_auto_sync(self) -> None:
        self.stop_auto_sync()
        self._timer = threading.Timer(self.interval_seconds, self._scheduled_sync)
        self._timer.daemon = True
        self._timer.start()

    def stop_auto_sync(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def manual_sync(self) -> Dict[str, Any]:
        return self.sync_now(reason="manual")

    def sync_now(self, reason: str = "auto") -> Dict[str, Any]:
        with self._lock:
            if self._syncing:
                return {"ok": False, "reason": "sync_already_running"}
            self._syncing = True
        try:
            backup_service.backup("before_sync")
            pushed = self._push_changed_records()
            pulled = self._pull_bridge_records()
            self._update_sync_state(True, reason, pushed, pulled)
            backup_service.backup("after_sync")
            return {"ok": True, "pushed": pushed, "pulled": pulled}
        except Exception as exc:
            self._queue_failure(str(exc))
            self._update_sync_state(False, reason, 0, 0, str(exc))
            return {"ok": False, "error": str(exc)}
        finally:
            with self._lock:
                self._syncing = False

    def retry_failed_syncs(self) -> Dict[str, Any]:
        state = local_storage.read_all().get("sync_state", {})
        queue = state.get("failed_queue", [])
        if not queue:
            return {"ok": True, "retried": 0}
        result = self.sync_now(reason="retry")
        if result.get("ok"):
            payload = local_storage.read_all()
            payload.setdefault("sync_state", {})["failed_queue"] = []
            local_storage.replace_all(payload)
        result["retried"] = len(queue)
        return result

    def _scheduled_sync(self) -> None:
        self.sync_now(reason="auto")
        self.start_auto_sync()

    def _push_changed_records(self) -> int:
        changed = local_storage.changed_records()
        if not any(changed.values()):
            return 0
        client = self._client()
        bridge_doc = {
            "id": str(uuid.uuid4()),
            "direction": "local_to_bridge",
            "payload": changed,
            "created_at": self._now(),
            "source": self._machine_source(),
        }
        client.table(BRIDGE_TABLE).insert(bridge_doc).execute()
        for collection, rows in changed.items():
            local_storage.mark_clean(collection, [str(row.get("id") or row.get("uid")) for row in rows])
        return sum(len(rows) for rows in changed.values())

    def _pull_bridge_records(self) -> int:
        client = self._client()
        response = client.table(BRIDGE_TABLE).select("*").neq("source", self._machine_source()).execute()
        rows = getattr(response, "data", None) or []
        imported = 0
        delete_ids: List[str] = []
        for row in rows:
            payload = row.get("payload") or {}
            if isinstance(payload, str):
                payload = json.loads(payload)
            imported += self._merge_payload(payload)
            if row.get("id"):
                delete_ids.append(str(row["id"]))
        for bridge_id in delete_ids:
            client.table(BRIDGE_TABLE).delete().eq("id", bridge_id).execute()
        return imported

    def _merge_payload(self, payload: Dict[str, List[dict]]) -> int:
        count = 0
        for collection, records in payload.items():
            target = "service_requests" if collection in ("service_requests", "sr_entries") else collection
            for record in records:
                record = dict(record)
                record["_dirty"] = False
                doc_id = str(record.get("id") or record.get("uid") or uuid.uuid4())
                local_storage.upsert_document(target, record, doc_id=doc_id)
                count += 1
        return count

    def _client(self):
        env = self.ensure_env()
        key = env["SUPABASE_KEY"]
        if not key or key == SUPABASE_KEY_PLACEHOLDER:
            raise RuntimeError("SUPABASE_KEY is not configured. Add the project publishable key to .env.")
        if importlib.util.find_spec("supabase") is not None:
            supabase_mod = importlib.import_module("supabase")
            return supabase_mod.create_client(env["SUPABASE_URL"], key)
        return RestBridgeClient(env["SUPABASE_URL"], key)

    def _update_sync_state(self, ok: bool, reason: str, pushed: int, pulled: int, error: str = "") -> None:
        payload = local_storage.read_all()
        state = payload.setdefault("sync_state", {})
        state.update({
            "last_sync_at": self._now(),
            "last_sync_ok": ok,
            "last_sync_reason": reason,
            "last_pushed": pushed,
            "last_pulled": pulled,
            "last_error": error,
        })
        local_storage.replace_all(payload)

    def _queue_failure(self, error: str) -> None:
        payload = local_storage.read_all()
        queue = payload.setdefault("sync_state", {}).setdefault("failed_queue", [])
        queue.append({"id": str(uuid.uuid4()), "error": error, "created_at": self._now()})
        local_storage.replace_all(payload)

    def _machine_source(self) -> str:
        return os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "local_pc"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()


class RestBridgeClient:
    """Small PostgREST-compatible fallback client used when supabase-py is absent."""

    def __init__(self, url: str, key: str) -> None:
        self.url = url.rstrip("/")
        self.key = key

    def table(self, name: str) -> "RestTable":
        return RestTable(self.url, self.key, name)


class RestResult:
    def __init__(self, data: Any) -> None:
        self.data = data


class RestTable:
    def __init__(self, url: str, key: str, name: str) -> None:
        self.base = f"{url}/rest/v1/{name}"
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self._params: Dict[str, str] = {}
        self._method = "GET"
        self._payload: Any = None

    def insert(self, payload: dict) -> "RestTable":
        self._method = "POST"
        self._payload = payload
        return self

    def select(self, fields: str) -> "RestTable":
        self._method = "GET"
        self._params["select"] = fields
        return self

    def neq(self, field: str, value: Any) -> "RestTable":
        self._params[field] = f"neq.{value}"
        return self

    def delete(self) -> "RestTable":
        self._method = "DELETE"
        return self

    def eq(self, field: str, value: Any) -> "RestTable":
        self._params[field] = f"eq.{value}"
        return self

    def execute(self) -> RestResult:
        response = requests.request(
            self._method,
            self.base,
            headers=self.headers,
            params=self._params,
            json=self._payload,
            timeout=15,
        )
        response.raise_for_status()
        if not response.text:
            return RestResult([])
        return RestResult(response.json())


sync_service = SyncService()
