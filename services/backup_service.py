"""Encrypted timestamped backup service for the local master JSON file."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from services.encryption_service import encryption_service
from services.local_storage_service import MASTER_DATA_PATH, local_storage


class BackupService:
    def __init__(self, backup_dir: str | Path = "backups") -> None:
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def backup(self, event: str) -> Path:
        """Create an encrypted backup for startup/shutdown/sync/archive events."""
        payload = local_storage.read_all()
        snapshot = {
            "event": event,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": str(MASTER_DATA_PATH),
            "payload": payload,
        }
        raw = json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode("utf-8")
        encrypted = encryption_service.encrypt_bytes(raw)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        path = self.backup_dir / f"{stamp}_{event}.backup"
        path.write_bytes(encrypted)
        return path

    def restore_backup(self, backup_path: str | Path) -> Dict[str, Any]:
        raw = encryption_service.decrypt_bytes(Path(backup_path).read_bytes())
        snapshot = json.loads(raw.decode("utf-8"))
        local_storage.replace_all(snapshot["payload"])
        return snapshot

    def export_backup_zip(self, event: str = "manual") -> Path:
        backup_path = self.backup(event)
        zip_path = backup_path.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(backup_path, arcname=backup_path.name)
        return zip_path


backup_service = BackupService()
