# services/sync_service.py
"""
Sync Engine — Phase 2.

Replaces the stub SyncNowWorker that returned {"ok": True, "Offline mode"}.

Architecture:
  1. Local JSON is the primary write surface (fast, offline-safe).
     Every create/update sets _dirty=True on the record.
  2. This engine reads all _dirty records and pushes them to Supabase.
  3. On success, _dirty is cleared via local_storage.mark_clean().
  4. Failed records stay dirty and are retried on next sync.
  5. Pull (cloud → local) is done on login and on-demand.

Sync is always run in a QThread worker — never on the main thread.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from PyQt6.QtCore import QThread, pyqtSignal

from services.local_storage_service import local_storage
from services.supabase_service import supabase_service, SyncStatus


# ── Sync result dataclass ─────────────────────────────────────────────────────

class SyncResult:
    def __init__(self):
        self.pushed:  int = 0
        self.pulled:  int = 0
        self.failed:  int = 0
        self.errors:  List[str] = []
        self.ok:      bool = False
        self.message: str  = ""

    def to_dict(self) -> dict:
        return {
            "ok":      self.ok,
            "pushed":  self.pushed,
            "pulled":  self.pulled,
            "failed":  self.failed,
            "errors":  self.errors,
            "message": self.message,
        }


# ── Push engine (local → Supabase) ───────────────────────────────────────────

SYNCABLE_COLLECTIONS = [
    "users",
    "service_requests",
    "tasks",
    "reports",
    "logs",
]


def push_dirty_records() -> SyncResult:
    """
    Find all records with _dirty=True and push them to Supabase.
    Returns a SyncResult with counts and any errors.
    This is safe to call from any thread.
    """
    result = SyncResult()

    if not supabase_service.is_configured():
        result.message = "Supabase not configured — skipping push."
        result.ok = True  # not an error, just not set up
        return result

    dirty = local_storage.changed_records()
    total_dirty = sum(len(v) for v in dirty.values())

    if total_dirty == 0:
        result.ok      = True
        result.message = "All records up to date — nothing to push."
        return result

    for collection, records in dirty.items():
        if not records:
            continue
        ok_count, fail_count = supabase_service.upsert_many(collection, records)
        result.pushed += ok_count
        result.failed += fail_count

        if fail_count > 0:
            result.errors.append(
                f"{collection}: {fail_count} record(s) failed — {supabase_service.last_error}"
            )
        elif ok_count > 0:
            # Mark pushed records as clean
            ids = [
                str(r.get("id") or r.get("uid") or r.get("sr_id") or "")
                for r in records
            ]
            local_storage.mark_clean(collection, [i for i in ids if i])

    result.ok = result.failed == 0
    result.message = (
        f"Pushed {result.pushed} record(s) to Supabase."
        if result.ok
        else f"Pushed {result.pushed}, failed {result.failed}. Check errors."
    )
    if result.ok:
        supabase_service.mark_sync_done()

    return result


# ── Pull engine (Supabase → local) ───────────────────────────────────────────

def pull_from_supabase(
    since_iso: str | None = None,
    collections: List[str] | None = None
) -> SyncResult:
    """
    Pull records from Supabase and merge them into local storage.
    `since_iso`  — if set, only pull records updated after this timestamp (delta sync).
    `collections` — if set, only pull these collections (default: all syncable).
    """
    result = SyncResult()

    if not supabase_service.is_configured():
        result.message = "Supabase not configured — skipping pull."
        result.ok = True
        return result

    targets = collections or SYNCABLE_COLLECTIONS

    for collection in targets:
        try:
            remote_records = supabase_service.pull_collection(collection, since_iso)
            if not remote_records:
                continue

            for record in remote_records:
                doc_id = str(record.get("id") or record.get("uid") or "")
                if not doc_id:
                    continue

                existing = local_storage.get_document(collection, doc_id)
                if existing is None:
                    # New record from cloud — create locally
                    record.pop("_dirty", None)
                    local_storage.create_document(collection, record, doc_id=doc_id)
                    result.pulled += 1
                else:
                    # Conflict resolution: cloud wins for pull operations.
                    # Dirty local records are NOT overwritten here —
                    # they will be pushed on the next push cycle.
                    if not existing.get("_dirty", False):
                        update_data = {k: v for k, v in record.items()
                                      if k not in ("_dirty",)}
                        local_storage.update_document(collection, doc_id, update_data)
                        result.pulled += 1

        except Exception as e:
            result.errors.append(f"{collection} pull error: {e}")
            result.failed += 1

    result.ok      = result.failed == 0
    result.message = (
        f"Pulled {result.pulled} record(s) from Supabase."
        if result.ok
        else f"Pull completed with {result.failed} error(s)."
    )
    return result


# ── QThread workers ───────────────────────────────────────────────────────────

class SyncNowWorker(QThread):
    """
    Push all dirty local records to Supabase.
    Replaces the old stub that returned {"ok": True, "Offline mode"}.
    """
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)

    def run(self):
        try:
            from services.config_service import global_config
            if global_config.get_val("sync_enabled") != "true":
                self.done.emit({
                    "ok":      True,
                    "message": "Cloud sync is disabled. Enable it in Admin Settings → Cloud Sync.",
                    "pushed":  0, "pulled": 0, "failed": 0, "errors": [],
                })
                return

            result = push_dirty_records()
            self.done.emit(result.to_dict())
        except Exception as e:
            self.error.emit(str(e))


class FullSyncWorker(QThread):
    """
    Bi-directional sync: push dirty records, then pull new remote records.
    Used on login or manual full-sync trigger.
    """
    progress = pyqtSignal(str)
    done     = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, since_iso: str | None = None):
        super().__init__()
        self.since_iso = since_iso

    def run(self):
        try:
            from services.config_service import global_config
            if global_config.get_val("sync_enabled") != "true":
                self.done.emit({"ok": True, "message": "Sync disabled.",
                                "pushed": 0, "pulled": 0, "failed": 0, "errors": []})
                return

            self.progress.emit("Testing connection…")
            ok, msg = supabase_service.test_connection()
            if not ok:
                self.done.emit({"ok": False, "message": msg,
                                "pushed": 0, "pulled": 0, "failed": 0, "errors": [msg]})
                return

            self.progress.emit("Pushing local changes…")
            push_result = push_dirty_records()

            self.progress.emit("Pulling cloud updates…")
            pull_result = pull_from_supabase(since_iso=self.since_iso)

            combined = {
                "ok":      push_result.ok and pull_result.ok,
                "pushed":  push_result.pushed,
                "pulled":  pull_result.pulled,
                "failed":  push_result.failed + pull_result.failed,
                "errors":  push_result.errors + pull_result.errors,
                "message": (
                    f"Sync complete: {push_result.pushed} pushed, "
                    f"{pull_result.pulled} pulled."
                ),
            }
            self.done.emit(combined)

        except Exception as e:
            self.error.emit(str(e))


class ConnectionTestWorker(QThread):
    """Quick test for the Supabase connection from Admin Settings."""
    done = pyqtSignal(bool, str)

    def run(self):
        ok, msg = supabase_service.test_connection()
        self.done.emit(ok, msg)
