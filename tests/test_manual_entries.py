from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.manual_entry import ManualObjectCreate, ManualObjectFromSourceCreate, ManualSourceAttachmentCreate
from app.schemas.source_reference import SourceReferenceCreate


def _source() -> SourceReferenceCreate:
    return SourceReferenceCreate(
        document_id=uuid4(),
        chunk_id=uuid4(),
        quote_text="forras idezet",
        quote_char_start=0,
        quote_char_end=12,
        source_kind="chunk_quote",
    )


def test_manual_entity_requires_source_and_entity_fields() -> None:
    payload = ManualObjectCreate(
        source_reference=_source(),
        object_type="entity",
        entity_type="person",
        canonical_name="Dupin",
    )

    assert payload.source_reference.quote_text == "forras idezet"
    assert payload.entity_type == "person"


def test_manual_claim_rejects_missing_claim_text() -> None:
    with pytest.raises(ValidationError):
        ManualObjectCreate(source_reference=_source(), object_type="claim")


def test_manual_object_from_existing_source_uses_same_field_rules() -> None:
    payload = ManualObjectFromSourceCreate(
        object_type="missing_item_candidate",
        missing_item_type="attachment",
        referenced_item_text="1. szamu melleklet",
        description="A forras hivatkozik a mellekletre.",
    )

    assert payload.object_type == "missing_item_candidate"


def test_manual_source_attachment_accepts_supported_target_type() -> None:
    target_object_id = uuid4()
    payload = ManualSourceAttachmentCreate(
        source_reference=_source(),
        target_object_type="event",
        target_object_id=target_object_id,
    )

    assert payload.target_object_type == "event"
    assert payload.target_object_id == target_object_id


def test_manual_source_attachment_rejects_unsupported_target_type() -> None:
    with pytest.raises(ValidationError):
        ManualSourceAttachmentCreate(
            source_reference=_source(),
            target_object_type="summary_item",
            target_object_id=uuid4(),
        )
