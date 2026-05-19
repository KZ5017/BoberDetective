from uuid import uuid4

import pytest

from app.models.audit import AuditEventModel
from app.models.document import DocumentModel
from app.models.user import UserModel
from app.services.documents import (
    DocumentLifecycleError,
    DocumentNotFoundError,
    update_document_lifecycle_status,
)


def test_document_lifecycle_update_changes_status_and_writes_audit(monkeypatch, tmp_path) -> None:
    case_id = uuid4()
    document_id = uuid4()
    user = UserModel(id=uuid4(), username="dev", display_name="Development User", role="admin", is_active=True)
    document = DocumentModel(
        id=document_id,
        case_id=case_id,
        original_filename="irat.pdf",
        stored_path=str(tmp_path / "irat.pdf"),
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=12,
        sha256_hash="a" * 64,
        imported_by_user_id=user.id,
        processing_status="processed",
        lifecycle_status="active",
    )
    db = _FakeDocumentDb(document=document, user=user)

    class _NoopJsonlAuditWriter:
        def __init__(self, storage) -> None:
            self.storage = storage

        def write(self, event) -> None:
            return None

    monkeypatch.setattr("app.services.documents.JsonlAuditWriter", _NoopJsonlAuditWriter)

    updated = update_document_lifecycle_status(
        db,
        case_id,
        document_id,
        "excluded",
        reason="Rossz feldolgozasi alapanyag.",
    )

    assert updated.lifecycle_status == "excluded"
    assert updated.lifecycle_status_reason == "Rossz feldolgozasi alapanyag."
    assert updated.lifecycle_status_changed_by_user_id == user.id
    assert updated.lifecycle_status_changed_at is not None
    audit_events = [item for item in db.added if isinstance(item, AuditEventModel)]
    assert len(audit_events) == 1
    assert audit_events[0].event_type == "document_excluded"
    assert audit_events[0].input_summary["previous_lifecycle_status"] == "active"
    assert audit_events[0].input_summary["new_lifecycle_status"] == "excluded"
    assert audit_events[0].input_summary["reason"] == "Rossz feldolgozasi alapanyag."
    assert audit_events[0].output_summary["changed"] is True
    assert db.committed is True


def test_document_lifecycle_restore_uses_restore_audit_event(monkeypatch, tmp_path) -> None:
    case_id = uuid4()
    document_id = uuid4()
    user = UserModel(id=uuid4(), username="dev", display_name="Development User", role="admin", is_active=True)
    document = DocumentModel(
        id=document_id,
        case_id=case_id,
        original_filename="irat.pdf",
        stored_path=str(tmp_path / "irat.pdf"),
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=12,
        sha256_hash="a" * 64,
        imported_by_user_id=user.id,
        processing_status="processed",
        lifecycle_status="archived",
    )
    db = _FakeDocumentDb(document=document, user=user)

    class _NoopJsonlAuditWriter:
        def __init__(self, storage) -> None:
            self.storage = storage

        def write(self, event) -> None:
            return None

    monkeypatch.setattr("app.services.documents.JsonlAuditWriter", _NoopJsonlAuditWriter)

    update_document_lifecycle_status(db, case_id, document_id, "active")

    audit_events = [item for item in db.added if isinstance(item, AuditEventModel)]
    assert len(audit_events) == 1
    assert audit_events[0].event_type == "document_restored"
    assert document.lifecycle_status == "active"


def test_document_lifecycle_update_rejects_other_case_document() -> None:
    document = DocumentModel(
        id=uuid4(),
        case_id=uuid4(),
        original_filename="irat.pdf",
        stored_path="/tmp/irat.pdf",
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=12,
        sha256_hash="a" * 64,
        imported_by_user_id=uuid4(),
        processing_status="processed",
        lifecycle_status="active",
    )
    db = _FakeDocumentDb(document=document)

    with pytest.raises(DocumentNotFoundError):
        update_document_lifecycle_status(db, uuid4(), document.id, "excluded")


def test_document_lifecycle_update_rejects_unknown_status() -> None:
    db = _FakeDocumentDb(document=None)

    with pytest.raises(DocumentLifecycleError):
        update_document_lifecycle_status(db, uuid4(), uuid4(), "discarded")


class _ScalarResult:
    def __init__(self, value) -> None:
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeDocumentDb:
    def __init__(self, document: DocumentModel | None, user: UserModel | None = None) -> None:
        self.document = document
        self.user = user
        self.added = []
        self.committed = False

    def get(self, model, object_id):
        if model is DocumentModel and self.document is not None and object_id == self.document.id:
            return self.document
        return None

    def execute(self, statement):
        return _ScalarResult(self.user)

    def add(self, item) -> None:
        self.added.append(item)

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        self.committed = True

    def refresh(self, item) -> None:
        return None
