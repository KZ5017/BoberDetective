import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from uuid import uuid4

from app.core.document_taxonomy import (
    default_document_taxonomy_codes,
    document_taxonomy_labels,
    find_document_type,
    validate_document_taxonomy,
)
from app.main import create_app
from app.models.audit import AuditEventModel
from app.models.document import DocumentModel
from app.models.user import UserModel
from app.schemas.document import DocumentImportMetadata, DocumentTaxonomyUpdateRequest
from app.services.documents import DocumentNotFoundError, update_document_taxonomy


def test_document_taxonomy_endpoint_lists_groups_and_types() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/document-taxonomy")

    assert response.status_code == 200
    data = response.json()["data"]
    group_codes = {group["code"] for group in data}
    assert "authority_decisions" in group_codes
    assert "uncategorized" in group_codes
    authority = next(group for group in data if group["code"] == "authority_decisions")
    assert any(document_type["code"] == "hatarozat" for document_type in authority["types"])


def test_document_taxonomy_validation_accepts_known_pair() -> None:
    validate_document_taxonomy("procedural_records", "jegyzokonyv")

    document_type = find_document_type("procedural_records", "jegyzokonyv")

    assert document_type is not None
    assert document_type.label == "Jegyzőkönyv"


def test_document_taxonomy_validation_rejects_type_from_other_group() -> None:
    with pytest.raises(ValueError):
        validate_document_taxonomy("authority_decisions", "jegyzokonyv")


def test_document_import_metadata_defaults_to_uncategorized_pair() -> None:
    metadata = DocumentImportMetadata()

    assert (metadata.document_group_code, metadata.document_type_code) == default_document_taxonomy_codes()


def test_document_import_metadata_rejects_invalid_taxonomy_pair() -> None:
    with pytest.raises(ValidationError):
        DocumentImportMetadata(document_group_code="authority_decisions", document_type_code="jegyzokonyv")


def test_document_taxonomy_labels_fall_back_to_codes_for_unknown_legacy_values() -> None:
    assert document_taxonomy_labels("unknown", "type") == ("unknown", "type")


def test_document_taxonomy_update_changes_metadata_and_writes_audit(monkeypatch, tmp_path) -> None:
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
        document_group_code="uncategorized",
        document_type_code="uncategorized",
        imported_by_user_id=user.id,
        processing_status="processed",
    )
    db = _FakeDocumentDb(document=document, user=user)

    class _NoopJsonlAuditWriter:
        def __init__(self, storage) -> None:
            self.storage = storage

        def write(self, event) -> None:
            return None

    monkeypatch.setattr("app.services.documents.JsonlAuditWriter", _NoopJsonlAuditWriter)

    updated = update_document_taxonomy(
        db,
        case_id,
        document_id,
        DocumentTaxonomyUpdateRequest(
            document_group_code="procedural_records",
            document_type_code="jegyzokonyv",
            comment="Téves importkori besorolás javítása",
        ),
    )

    assert updated.document_group_code == "procedural_records"
    assert updated.document_type_code == "jegyzokonyv"
    audit_events = [item for item in db.added if isinstance(item, AuditEventModel)]
    assert len(audit_events) == 1
    assert audit_events[0].event_type == "document_reclassified"
    assert audit_events[0].input_summary["previous_document_group_code"] == "uncategorized"
    assert audit_events[0].input_summary["previous_document_type_code"] == "uncategorized"
    assert audit_events[0].output_summary["document_group_code"] == "procedural_records"
    assert audit_events[0].output_summary["document_type_code"] == "jegyzokonyv"
    assert audit_events[0].output_summary["changed"] is True
    assert db.committed is True


def test_document_taxonomy_update_rejects_other_case_document() -> None:
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
    )
    db = _FakeDocumentDb(document=document)

    with pytest.raises(DocumentNotFoundError):
        update_document_taxonomy(
            db,
            uuid4(),
            document.id,
            DocumentTaxonomyUpdateRequest(document_group_code="procedural_records", document_type_code="jegyzokonyv"),
        )


def test_document_taxonomy_update_rejects_invalid_pair() -> None:
    with pytest.raises(ValidationError):
        DocumentTaxonomyUpdateRequest(document_group_code="authority_decisions", document_type_code="jegyzokonyv")


def test_document_taxonomy_update_noop_is_audited(monkeypatch, tmp_path) -> None:
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
        document_group_code="uncategorized",
        document_type_code="uncategorized",
        imported_by_user_id=user.id,
        processing_status="processed",
    )
    db = _FakeDocumentDb(document=document, user=user)

    class _NoopJsonlAuditWriter:
        def __init__(self, storage) -> None:
            self.storage = storage

        def write(self, event) -> None:
            return None

    monkeypatch.setattr("app.services.documents.JsonlAuditWriter", _NoopJsonlAuditWriter)

    update_document_taxonomy(
        db,
        case_id,
        document_id,
        DocumentTaxonomyUpdateRequest(document_group_code="uncategorized", document_type_code="uncategorized"),
    )

    audit_events = [item for item in db.added if isinstance(item, AuditEventModel)]
    assert len(audit_events) == 1
    assert audit_events[0].output_summary["changed"] is False


class _ScalarResult:
    def __init__(self, value) -> None:
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeDocumentDb:
    def __init__(self, document: DocumentModel, user: UserModel | None = None) -> None:
        self.document = document
        self.user = user
        self.added = []
        self.committed = False

    def get(self, model, object_id):
        if model is DocumentModel and object_id == self.document.id:
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
