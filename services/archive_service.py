"""Yearly archive service for the admin 'START NEW YEAR' feature."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from services.backup_service import backup_service
from services.local_storage_service import local_storage


class ArchiveService:
    def __init__(self, archive_dir: str | Path = "archives") -> None:
        self.archive_dir = Path(archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def start_new_year(self, archive_year: int | None = None, next_year: int | None = None) -> Path:
        """Compress the current dataset and reset active local data for the next year."""
        now = datetime.now(timezone.utc)
        archive_year = archive_year or now.year
        next_year = next_year or archive_year + 1
        backup_service.backup("before_archive_reset")
        payload = local_storage.read_all()
        payload.setdefault("archive", {})[str(archive_year)] = {
            "archived_at": now.isoformat(),
            "zip": f"archives/{archive_year}.zip",
            "record_counts": {
                "users": len(payload.get("users", [])),
                "tasks": len(payload.get("tasks", [])),
                "sr_entries": len(payload.get("sr_entries", [])),
                "reports": len(payload.get("reports", [])),
                "logs": len(payload.get("logs", [])),
            },
        }
        zip_path = self.archive_dir / f"{archive_year}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("master_data.json", json.dumps(payload, indent=2, ensure_ascii=False))
        local_storage.replace_all(payload)
        local_storage.reset_active_dataset(next_year)
        return zip_path

    def list_archives(self) -> Dict[str, Any]:
        return local_storage.read_all().get("archive", {})

    def load_archive(self, year: int) -> Dict[str, Any]:
        zip_path = self.archive_dir / f"{year}.zip"
        with zipfile.ZipFile(zip_path, "r") as zf:
            return json.loads(zf.read("master_data.json").decode("utf-8"))


archive_service = ArchiveService()
