# services/supabase_service.py
"""
Supabase Integration Service — Phase 2.

Architecture:
  LOCAL JSON  = primary write surface (fast, offline-safe)
  SUPABASE    = cloud mirror / source of truth for multi-device sync
  SYNC ENGINE = pushes dirty local records to Supabase on reconnect

This module wraps supabase-py and exposes a clean API that the rest of
the codebase uses. It never raises into the UI — all errors are caught,
logged, and surfaced via the SyncStatus enum.

Setup:
  1. Create a Supabase project at https://supabase.com
  2. Run the SQL in setup/supabase_schema.sql to create tables
  3. Set SUPABASE_URL and SUPABASE_KEY in Admin Settings → Cloud Sync
     (stored in global_config, NOT hardcoded here)
"""

from __future__ import annotations

import importlib
import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class SyncStatus(Enum):
    IDLE        = "idle"
    SYNCING     = "syncing"
    SUCCESS     = "success"
    ERROR       = "error"
    DISABLED    = "disabled"
    NO_NETWORK  = "no_network"
    NOT_CONFIG  = "not_configured"


class SupabaseService:
    """
    Thin wrapper around supabase-py.
    Lazy-initialised — safe to import even if supabase-py is not installed.
    """

    def __init__(self) -> None:
        self._client = None
        self._lock   = threading.Lock()
        self._status = SyncStatus.IDLE
        self._last_error: str = ""
        self._last_sync:  str = ""

    # ── Init / config ──────────────────────────────────────────────────────────

    def _get_config(self) -> tuple[str, str]:
        """Return (url, key) from global_config or environment."""
        import os
        from services.config_service import global_config
        cfg = global_config.get()
        url = cfg.get("supabase_url", "").strip() or os.getenv("SUPABASE_URL", "")
        key = cfg.get("supabase_key", "").strip() or os.getenv("SUPABASE_KEY", "")
        return url, key

    def _init_client(self) -> bool:
        """Lazy-init the Supabase client. Returns True if successful."""
        with self._lock:
            if self._client is not None:
                return True
            url, key = self._get_config()
            if not url or not key:
                self._status = SyncStatus.NOT_CONFIG
                self._last_error = "Supabase URL and Key not configured. Set them in Admin Settings → Cloud Sync."
                return False
            try:
                supabase_mod = importlib.import_module("supabase")
                create_client = getattr(supabase_mod, "create_client")
                self._client = create_client(url, key)
                self._status = SyncStatus.IDLE
                return True
            except ImportError:
                self._status = SyncStatus.ERROR
                self._last_error = (
                    "supabase-py is not installed.\n"
                    "Run: pip install supabase"
                )
                return False
            except Exception as e:
                self._status = SyncStatus.ERROR
                self._last_error = f"Supabase init failed: {e}"
                return False

    def reset_client(self) -> None:
        """Force re-init on next operation (call after config change)."""
        with self._lock:
            self._client = None
            self._status = SyncStatus.IDLE

    def is_configured(self) -> bool:
        url, key = self._get_config()
        return bool(url and key)

    @property
    def status(self) -> SyncStatus:
        return self._status

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def last_sync(self) -> str:
        return self._last_sync

    # ── Table mapping ─────────────────────────────────────────────────────────

    SUPABASE_TABLES = {
        "users":            "users",
        "service_requests": "sr_entries",
        "sr_entries":       "sr_entries",
        "tasks":            "tasks",
        "reports":          "reports",
        "audit_log":        "activity_logs",
        "logs":             "activity_logs",
        "pipeline_templates": "pipelines",
        "roles":            "roles",
    }

    def _table_name(self, collection: str) -> str:
        return self.SUPABASE_TABLES.get(collection, collection)

    # ── Read operations ────────────────────────────────────────────────────────

    def get_collection(self, collection: str) -> List[dict]:
        if not self._init_client():
            return []
        try:
            table = self._table_name(collection)
            resp  = self._client.table(table).select("*").execute()
            return resp.data or []
        except Exception as e:
            self._last_error = str(e)
            return []

    def get_document(self, collection: str, doc_id: str) -> Optional[dict]:
        if not self._init_client():
            return None
        try:
            table = self._table_name(collection)
            resp  = (self._client.table(table)
                     .select("*")
                     .eq("id", doc_id)
                     .limit(1)
                     .execute())
            return resp.data[0] if resp.data else None
        except Exception as e:
            self._last_error = str(e)
            return None

    # ── Write operations ───────────────────────────────────────────────────────

    def upsert_document(self, collection: str, doc: dict) -> bool:
        if not self._init_client():
            return False
        try:
            table   = self._table_name(collection)
            payload = self._clean_for_supabase(doc)
            (self._client.table(table)
             .upsert(payload, on_conflict="id")
             .execute())
            return True
        except Exception as e:
            self._last_error = f"Upsert {collection} failed: {e}"
            return False

    def upsert_many(self, collection: str, docs: List[dict]) -> tuple[int, int]:
        """Upsert a list of docs. Returns (success_count, fail_count)."""
        if not self._init_client() or not docs:
            return 0, len(docs)
        ok = fail = 0
        try:
            table    = self._table_name(collection)
            payloads = [self._clean_for_supabase(d) for d in docs]
            # Supabase supports batch upsert
            (self._client.table(table)
             .upsert(payloads, on_conflict="id")
             .execute())
            ok = len(docs)
        except Exception as e:
            # Fall back to one-by-one so we don't lose everything on one bad record
            self._last_error = f"Batch upsert partially failed: {e}"
            for doc in docs:
                if self.upsert_document(collection, doc):
                    ok += 1
                else:
                    fail += 1
        return ok, fail

    def delete_document(self, collection: str, doc_id: str) -> bool:
        if not self._init_client():
            return False
        try:
            table = self._table_name(collection)
            (self._client.table(table)
             .delete()
             .eq("id", doc_id)
             .execute())
            return True
        except Exception as e:
            self._last_error = f"Delete {collection}/{doc_id} failed: {e}"
            return False

    # ── Sync helpers ───────────────────────────────────────────────────────────

    def test_connection(self) -> tuple[bool, str]:
        """Quick connectivity test. Returns (ok, message)."""
        if not self._init_client():
            return False, self._last_error
        try:
            # Lightweight query — just check auth
            self._client.table("users").select("id").limit(1).execute()
            return True, "Connected to Supabase successfully."
        except Exception as e:
            return False, f"Connection test failed: {e}"

    def pull_collection(self, collection: str,
                        since_iso: Optional[str] = None) -> List[dict]:
        """
        Pull records from Supabase, optionally only those updated after `since_iso`.
        Used during initial sync or partial refresh.
        """
        if not self._init_client():
            return []
        try:
            table = self._table_name(collection)
            query = self._client.table(table).select("*")
            if since_iso:
                query = query.gte("updated_at", since_iso)
            resp = query.order("updated_at", desc=True).execute()
            return resp.data or []
        except Exception as e:
            self._last_error = str(e)
            return []

    def mark_sync_done(self) -> None:
        self._last_sync = datetime.now(timezone.utc).isoformat()
        self._status    = SyncStatus.SUCCESS

    # ── Private helpers ────────────────────────────────────────────────────────

    def _clean_for_supabase(self, doc: dict) -> dict:
        """
        Prepare a local document for Supabase upsert.
        - Removes local-only metadata fields
        - Ensures 'id' column is present (Supabase primary key)
        - Strips password hashes (never sent to cloud)
        """
        cleaned = dict(doc)
        # Remove local-only fields
        for field in ("_dirty", "password_hash", "password",
                      "is_master_admin", "_role_doc"):
            cleaned.pop(field, None)
        # Supabase wants 'id' as the PK column
        if "id" not in cleaned:
            uid = cleaned.get("uid") or cleaned.get("sr_id")
            if uid:
                cleaned["id"] = uid
        return cleaned


supabase_service = SupabaseService()
