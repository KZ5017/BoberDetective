from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.source_reference import SourceReferenceCreate
from app.services.source_references import SourceReferenceValidationError, _resolve_quote_span


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
