"""Google Sheets and Excel import/export helpers for local SR entries."""

from __future__ import annotations

import csv
import importlib
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from services.local_storage_service import local_storage
from utils.helpers import utc_now_iso


class GoogleSheetService:
    def __init__(self) -> None:
        self._timer: threading.Timer | None = None
        self._interval_seconds = 300

    def import_sr_entries(self, records: Iterable[Dict[str, Any]]) -> int:
        """Import SR dictionaries with duplicate detection into local storage."""
        existing = local_storage.get_collection("service_requests")
        seen = {self._fingerprint(row) for row in existing}
        count = 0
        for row in records:
            fp = self._fingerprint(row)
            if fp in seen:
                continue
            data = dict(row)
            data.setdefault("status", "Open")
            data.setdefault("created_at", utc_now_iso())
            data.setdefault("updated_at", data["created_at"])
            local_storage.create_document("service_requests", data)
            seen.add(fp)
            count += 1
        return count

    def import_from_google_sheet(self, credentials_json: str | Path, sheet_name: str, worksheet_name: str | None = None) -> int:
        gspread = importlib.import_module("gspread")
        oauth_service_account = importlib.import_module("oauth2client.service_account")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = oauth_service_account.ServiceAccountCredentials.from_json_keyfile_name(str(credentials_json), scope)
        client = gspread.authorize(creds)
        sheet = client.open(sheet_name)
        worksheet = sheet.worksheet(worksheet_name) if worksheet_name else sheet.sheet1
        return self.import_sr_entries(worksheet.get_all_records())

    def import_from_excel(self, excel_path: str | Path, sheet_name: str | int | None = 0) -> int:
        pandas = importlib.import_module("pandas")
        frame = pandas.read_excel(excel_path, sheet_name=sheet_name)
        return self.import_sr_entries(frame.fillna("").to_dict("records"))

    def export_to_excel(self, excel_path: str | Path, records: Sequence[Dict[str, Any]] | None = None) -> Path:
        pandas = importlib.import_module("pandas")
        records = list(records) if records is not None else local_storage.get_collection("service_requests")
        pandas.DataFrame(records).to_excel(excel_path, index=False)
        return Path(excel_path)

    def import_from_csv(self, csv_path: str | Path) -> int:
        with Path(csv_path).open(newline="", encoding="utf-8") as fh:
            return self.import_sr_entries(csv.DictReader(fh))

    def schedule_import(self, credentials_json: str | Path, sheet_name: str, worksheet_name: str | None = None, interval_seconds: int = 300) -> None:
        self.stop_scheduled_import()
        self._interval_seconds = interval_seconds

        def _run() -> None:
            self.import_from_google_sheet(credentials_json, sheet_name, worksheet_name)
            self.schedule_import(credentials_json, sheet_name, worksheet_name, self._interval_seconds)

        self._timer = threading.Timer(interval_seconds, _run)
        self._timer.daemon = True
        self._timer.start()

    def stop_scheduled_import(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _fingerprint(self, row: Dict[str, Any]) -> str:
        candidates = ["id", "sr_id", "ticket_id", "request_id", "title", "description"]
        parts = [str(row.get(key, "")).strip().lower() for key in candidates]
        return "|".join(parts)


google_sheet_service = GoogleSheetService()
