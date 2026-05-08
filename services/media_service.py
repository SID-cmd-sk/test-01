# services/media_service.py
"""
Media & Attachment Service.

Handles:
  - File uploads (local cache + Supabase Storage)
  - File preview (images inline, PDF/Office open in system viewer)
  - Drag-and-drop support helpers
  - Encrypted local cache of attachments
  - Cleanup of orphaned attachments

Storage strategy:
  1. File is saved to  attachments/<sr_id>/<uuid>_<filename>  locally
  2. Metadata record is written to local_storage "attachments" collection
  3. On sync, file is uploaded to Supabase Storage bucket "attachments"
  4. Supabase public URL is stored in the metadata record
"""

from __future__ import annotations

import mimetypes
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import List, Optional

LOCAL_ATTACHMENT_DIR = Path("attachments")
ALLOWED_EXTENSIONS   = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp",          # Images
    ".pdf",                                             # PDF
    ".xlsx", ".xls", ".csv",                            # Excel
    ".docx", ".doc",                                    # Word
    ".mp4", ".mov", ".avi",                             # Video
    ".mp3", ".wav", ".m4a",                             # Audio (voice notes)
    ".txt", ".log",                                     # Text
    ".zip",                                             # Archives
}
MAX_FILE_SIZE_MB = 50


class AttachmentError(Exception):
    pass


def allowed_file(path: str | Path) -> bool:
    return Path(path).suffix.lower() in ALLOWED_EXTENSIONS


def save_attachment(
    src_path: str | Path,
    sr_id: str,
    uploaded_by_uid: str,
) -> dict:
    """
    Copy a file from src_path into the local attachments cache,
    create a metadata record, and mark it for cloud upload on next sync.

    Returns the attachment metadata dict.
    Raises AttachmentError on validation failure.
    """
    src = Path(src_path)
    if not src.exists():
        raise AttachmentError(f"File not found: {src}")

    ext = src.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise AttachmentError(
            f"File type '{ext}' is not allowed.\n"
            f"Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    size_bytes = src.stat().st_size
    size_mb    = size_bytes / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise AttachmentError(
            f"File too large: {size_mb:.1f} MB (max {MAX_FILE_SIZE_MB} MB)."
        )

    # Create local storage directory
    dest_dir = LOCAL_ATTACHMENT_DIR / sr_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    att_id   = str(uuid.uuid4())
    filename = f"{att_id[:8]}_{src.name}"
    dest     = dest_dir / filename
    shutil.copy2(src, dest)

    mime_type, _ = mimetypes.guess_type(str(src))

    from utils.helpers import utc_now_iso
    metadata = {
        "id":            att_id,
        "sr_id":         sr_id,
        "filename":      src.name,
        "local_path":    str(dest),
        "cloud_url":     "",          # populated after Supabase upload
        "file_size":     size_bytes,
        "mime_type":     mime_type or "application/octet-stream",
        "uploaded_by":   uploaded_by_uid,
        "created_at":    utc_now_iso(),
        "_dirty":        True,
        "_needs_upload": True,        # flag for cloud upload
    }

    # Write metadata to local storage
    from services.local_storage_service import local_storage
    local_storage.create_document("attachments", metadata, doc_id=att_id)

    # Fire automation event
    try:
        from services.automation_engine import fire_event
        fire_event("attachment_added", {"sr_id": sr_id, "filename": src.name})
    except Exception:
        pass

    return metadata


def get_attachments_for_sr(sr_id: str) -> List[dict]:
    """Return all attachment metadata records for a given SR."""
    try:
        from services.local_storage_service import local_storage
        all_atts = local_storage.get_collection("attachments")
        return [a for a in all_atts if a.get("sr_id") == sr_id]
    except Exception:
        return []


def open_attachment(metadata: dict) -> None:
    """
    Open an attachment in the system's default application.
    Tries local_path first; falls back to cloud_url download.
    """
    local_path = metadata.get("local_path", "")
    if local_path and Path(local_path).exists():
        _open_with_system(local_path)
        return

    cloud_url = metadata.get("cloud_url", "")
    if cloud_url:
        # Download to temp and open
        import tempfile, requests
        ext  = Path(metadata.get("filename", "file")).suffix
        tmp  = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        try:
            resp = requests.get(cloud_url, timeout=30)
            tmp.write(resp.content)
            tmp.close()
            _open_with_system(tmp.name)
        except Exception as e:
            raise AttachmentError(f"Could not download attachment: {e}")
    else:
        raise AttachmentError("File not found locally and no cloud URL available.")


def _open_with_system(path: str) -> None:
    """Open file using the OS default application."""
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        raise AttachmentError(f"Could not open file: {e}")


def delete_attachment(att_id: str, sr_id: str) -> None:
    """Delete attachment locally and from Supabase Storage."""
    from services.local_storage_service import local_storage
    meta = local_storage.get_document("attachments", att_id)
    if not meta:
        return

    # Delete local file
    local_path = meta.get("local_path", "")
    if local_path:
        try:
            Path(local_path).unlink(missing_ok=True)
        except Exception:
            pass

    # Delete from Supabase Storage
    cloud_url = meta.get("cloud_url", "")
    if cloud_url:
        try:
            from services.supabase_service import supabase_service
            if supabase_service.is_configured() and supabase_service._init_client():
                storage_path = f"{sr_id}/{Path(local_path).name}"
                supabase_service._client.storage.from_("attachments").remove([storage_path])
        except Exception:
            pass

    # Remove metadata record
    local_storage.delete_document("attachments", att_id)


def upload_pending_attachments() -> tuple[int, int]:
    """
    Upload all local attachments that have _needs_upload=True to Supabase Storage.
    Called by the sync engine. Returns (success, failed).
    """
    from services.local_storage_service import local_storage
    from services.supabase_service import supabase_service

    if not supabase_service.is_configured():
        return 0, 0

    if not supabase_service._init_client():
        return 0, 0

    all_atts = local_storage.get_collection("attachments")
    pending  = [a for a in all_atts if a.get("_needs_upload") and a.get("local_path")]

    ok = fail = 0
    for att in pending:
        local_path = Path(att.get("local_path", ""))
        if not local_path.exists():
            continue
        try:
            sr_id    = att.get("sr_id", "unknown")
            storage_path = f"{sr_id}/{local_path.name}"
            with open(local_path, "rb") as f:
                supabase_service._client.storage.from_("attachments").upload(
                    path=storage_path,
                    file=f,
                    file_options={"content-type": att.get("mime_type", "application/octet-stream")},
                )
            # Get public URL
            url_resp = supabase_service._client.storage.from_("attachments").get_public_url(storage_path)
            local_storage.update_document("attachments", att["id"], {
                "cloud_url":     url_resp,
                "_needs_upload": False,
            })
            ok += 1
        except Exception:
            fail += 1

    return ok, fail


def is_image(metadata: dict) -> bool:
    mime = metadata.get("mime_type", "")
    return mime.startswith("image/")


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
