import json
from pathlib import Path

from services.local_storage_service import LocalStorageService
from utils.helpers import validate_password
from utils.auth import session


def test_unknown_and_attachment_collections_survive_normalization(tmp_path):
    db_path = tmp_path / "master_data.json"
    store = LocalStorageService(db_path)
    payload = store.read_all()
    payload["attachments"] = [{"id": "a1", "sr_id": "sr1", "_dirty": False}]
    payload["future_collection"] = [{"id": "x"}]
    store.replace_all(payload)

    reloaded = LocalStorageService(db_path).read_all()
    assert reloaded["attachments"][0]["id"] == "a1"
    assert reloaded["future_collection"] == [{"id": "x"}]


def test_pulled_records_can_be_written_clean(tmp_path):
    store = LocalStorageService(tmp_path / "master_data.json")
    store.create_document("service_requests", {"id": "sr1", "title": "Cloud"}, doc_id="sr1", mark_dirty=False)
    doc = store.get_document("service_requests", "sr1")
    assert doc["_dirty"] is False

    store.update_document("service_requests", "sr1", {"title": "Cloud edit"}, mark_dirty=False)
    assert store.get_document("service_requests", "sr1")["_dirty"] is False
    assert store.changed_records()["service_requests"] == []


def test_soft_delete_creates_tombstone_then_purge(tmp_path):
    store = LocalStorageService(tmp_path / "master_data.json")
    store.create_document("attachments", {"id": "att1", "sr_id": "sr1"}, doc_id="att1")
    store.delete_document("attachments", "att1")

    assert store.get_collection("attachments") == []
    dirty = store.changed_records()["attachments"]
    assert dirty[0]["_deleted"] is True

    store.purge_deleted("attachments", ["att1"])
    assert store.read_all()["attachments"] == []


def test_corrupt_json_is_quarantined_and_recovers(tmp_path):
    db_path = tmp_path / "master_data.json"
    db_path.write_text("{not json", encoding="utf-8")
    store = LocalStorageService(db_path)
    payload = store.read_all()
    assert "recovery_warning" in payload["sync_state"]
    assert list(tmp_path.glob("master_data.corrupt.*.json"))


def test_password_validator_contract_is_consistent():
    assert validate_password("short1") == (False, "Password must be at least 8 characters.")
    assert validate_password("longpassword") == (False, "Password must include at least one letter and one number.")
    assert validate_password("StrongPass1") == (True, "")


def test_viewer_session_has_no_dangerous_permissions():
    session.set("u1", "v@example.com", "Viewer", "viewer")
    try:
        assert not session.can("create_user")
        assert not session.can("manage_settings")
    finally:
        session.clear()
