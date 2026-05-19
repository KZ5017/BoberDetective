from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.document import DocumentModel
from app.schemas.source_reference import SourceReferenceCreate
from app.services.source_references import SourceReferenceValidationError, _get_case_document, _resolve_quote_span


def test_source_reference_create_rejects_invalid_offsets() -> None:
    with pytest.raises(ValidationError):
        SourceReferenceCreate(
            document_id=uuid4(),
            chunk_id=uuid4(),
            quote_text="telefon",
            quote_char_start=10,
            quote_char_end=5,
        )


def test_resolve_quote_span_finds_quote_when_offsets_missing() -> None:
    assert _resolve_quote_span("alpha telefon beta", "telefon", None, None) == (6, 13)


def test_resolve_quote_span_rejects_missing_quote() -> None:
    with pytest.raises(SourceReferenceValidationError):
        _resolve_quote_span("alpha beta", "telefon", None, None)


def test_resolve_quote_span_rejects_mismatched_offsets() -> None:
    with pytest.raises(SourceReferenceValidationError):
        _resolve_quote_span("alpha telefon beta", "telefon", 0, 5)


def test_get_case_document_rejects_inactive_document() -> None:
    case_id = uuid4()
    document = DocumentModel(
        id=uuid4(),
        case_id=case_id,
        original_filename="irat.pdf",
        stored_path="/tmp/irat.pdf",
        mime_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=12,
        sha256_hash="a" * 64,
        imported_by_user_id=uuid4(),
        processing_status="processed",
        lifecycle_status="excluded",
    )

    with pytest.raises(SourceReferenceValidationError, match="Document is not active"):
        _get_case_document(_FakeDb(document), case_id, document.id)


class _FakeDb:
    def __init__(self, document: DocumentModel) -> None:
        self.document = document

    def get(self, model, object_id):
        if model is DocumentModel and object_id == self.document.id:
            return self.document
        return None
