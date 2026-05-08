from services.local_storage_service import LocalStorageService
from services import sync_service


class FakeSupabase:
    last_error = ""

    def __init__(self):
        self.deleted = []
        self.upserted = []
        self.remote = []

    def is_configured(self):
        return True

    def upsert_many(self, collection, docs):
        self.upserted.extend((collection, d["id"]) for d in docs)
        return len(docs), 0

    def delete_document(self, collection, doc_id):
        self.deleted.append((collection, doc_id))
        return True

    def pull_collection(self, collection, since_iso=None):
        return self.remote

    def mark_sync_done(self):
        pass


def test_push_handles_deletes_and_attachments(monkeypatch, tmp_path):
    store = LocalStorageService(tmp_path / "master_data.json")
    fake = FakeSupabase()
    monkeypatch.setattr(sync_service, "local_storage", store)
    monkeypatch.setattr(sync_service, "supabase_service", fake)
    monkeypatch.setattr("services.media_service.upload_pending_attachments", lambda: (0, 0))

    store.create_document("service_requests", {"id": "sr1", "title": "A"}, doc_id="sr1")
    store.create_document("attachments", {"id": "att1", "sr_id": "sr1"}, doc_id="att1")
    store.delete_document("attachments", "att1")

    result = sync_service.push_dirty_records()
    assert result.ok
    assert ("service_requests", "sr1") in fake.upserted
    assert ("attachments", "att1") in fake.deleted
    assert store.read_all()["attachments"] == []


def test_pull_writes_remote_records_clean(monkeypatch, tmp_path):
    store = LocalStorageService(tmp_path / "master_data.json")
    fake = FakeSupabase()
    fake.remote = [{"id": "sr-cloud", "title": "Remote", "updated_at": "2026-01-01T00:00:00+00:00"}]
    monkeypatch.setattr(sync_service, "local_storage", store)
    monkeypatch.setattr(sync_service, "supabase_service", fake)

    result = sync_service.pull_from_supabase(collections=["service_requests"])
    assert result.ok
    assert store.get_document("service_requests", "sr-cloud")["_dirty"] is False
    assert store.changed_records()["service_requests"] == []
