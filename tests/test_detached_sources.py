from uuid import uuid4

from app.models.source_reference import SourceReferenceModel
from app.services.detached_sources import create_detached_source_item


class _FakeDb:
    def __init__(self) -> None:
        self.added = []

    def add(self, item) -> None:
        self.added.append(item)

    def flush(self) -> None:
        return None


def test_create_detached_source_item_preserves_origin_and_source_snapshot() -> None:
    case_id = uuid4()
    user_id = uuid4()
    source_reference = SourceReferenceModel(
        id=uuid4(),
        case_id=case_id,
        document_id=uuid4(),
        page_id=uuid4(),
        chunk_id=uuid4(),
        page_number=7,
        quote_text="fontos idezet",
        quote_char_start=10,
        quote_char_end=22,
        citation_label="irat.pdf, chunk 3",
        source_kind="chunk_quote",
    )

    item = create_detached_source_item(
        _FakeDb(),
        case_id=case_id,
        source_reference=source_reference,
        detached_from_object_type="event",
        detached_from_object_id=uuid4(),
        detached_from_source_link_id=uuid4(),
        detached_from_source_link_type="event_source",
        object_title_snapshot="Esemeny cime",
        object_body_snapshot="Esemeny leirasa",
        object_subtype_snapshot="statement",
        object_review_status_snapshot="needs_review",
        source_validation_status_snapshot="source_valid",
        detach_comment="rossz forras",
        detached_by_user_id=user_id,
    )

    assert item.handling_status == "needs_review"
    assert item.reattached_to_object_type is None
    assert item.reattached_to_object_id is None
    assert item.reattached_to_object_title_snapshot is None
    assert item.detached_by_user_id == user_id
    assert item.object_title_snapshot == "Esemeny cime"
    assert item.detach_comment == "rossz forras"
    assert item.source_snapshot_json["quote_text"] == "fontos idezet"
    assert item.source_snapshot_json["citation_label"] == "irat.pdf, chunk 3"
