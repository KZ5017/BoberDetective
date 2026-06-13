from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.document import DocumentChunkModel, DocumentModel, DocumentPageModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.review_report import ReviewReportFilters, ReviewReportItem
from app.services.review_report import (
    ReviewReportValidationError,
    _build_counts,
    _filter_items,
    _report_source_from_reference,
    _source_excerpt,
)


class FakeDb:
    def __init__(self, values: dict[tuple[type, object], object]) -> None:
        self.values = values

    def get(self, model, object_id):
        return self.values.get((model, object_id))


def _item(object_type: str, review_status: str, source_validation_status: str) -> ReviewReportItem:
    return ReviewReportItem(
        object_type=object_type,
        object_id=uuid4(),
        title="item",
        body_text=None,
        subtype="subtype",
        review_status=review_status,
        source_validation_status=source_validation_status,
        created_by_analysis_run_id=uuid4(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        sources=[],
        reviews=[],
    )


def test_review_report_counts_known_statuses() -> None:
    counts = _build_counts(["needs_review", "needs_review", "verified", "rejected", "corrected"])

    assert counts.total == 5
    assert counts.needs_review == 2
    assert counts.verified == 1
    assert counts.rejected == 1
    assert counts.corrected == 1


def test_review_report_counts_missing_statuses_as_zero() -> None:
    counts = _build_counts(["verified"])

    assert counts.total == 1
    assert counts.needs_review == 0
    assert counts.verified == 1
    assert counts.rejected == 0


def test_review_report_filters_by_object_type_review_and_source_status() -> None:
    items = [
        _item("claim", "needs_review", "source_valid"),
        _item("contradiction_candidate", "needs_review", "source_valid"),
        _item("missing_item_candidate", "needs_review", "source_valid"),
        _item("entity", "needs_review", "source_valid"),
        _item("event", "verified", "source_valid"),
        _item("event", "needs_review", "source_invalid"),
    ]

    filtered = _filter_items(
        items,
        ReviewReportFilters(
            object_types=["contradiction_candidate", "entity", "event", "missing_item_candidate"],
            review_statuses=["needs_review"],
            source_validation_statuses=["source_valid"],
        ),
    )

    assert [(item.object_type, item.review_status) for item in filtered] == [
        ("contradiction_candidate", "needs_review"),
        ("missing_item_candidate", "needs_review"),
        ("entity", "needs_review"),
    ]


def test_review_report_filters_reject_unknown_values() -> None:
    with pytest.raises(ReviewReportValidationError):
        _filter_items([_item("claim", "needs_review", "source_valid")], ReviewReportFilters(object_types=["export"]))


def test_source_excerpt_returns_full_source_text_when_quote_matches() -> None:
    source_text = f"{'a' * 200}bizonyito idezet{'b' * 200}"

    excerpt, start, end = _source_excerpt(source_text, "bizonyito idezet", 200, 216)

    assert excerpt == source_text
    assert start == 0
    assert end == len(source_text)


def test_source_excerpt_falls_back_to_quote_search() -> None:
    excerpt, start, end = _source_excerpt("eleje keresett idezet vege", "keresett idezet", None, None)

    assert excerpt == "eleje keresett idezet vege"
    assert start == 0
    assert end == 26


def test_source_excerpt_can_include_unresolved_context_for_invalid_source() -> None:
    source_text = "ebben a szovegreszben kell ellenorizni a hibas idezetet"
    excerpt, start, end = _source_excerpt(
        source_text,
        "hibas LLM idezet",
        None,
        None,
        include_unresolved_context=True,
    )

    assert excerpt == source_text
    assert start == 0
    assert end == len(source_text)


def test_source_excerpt_hides_unresolved_context_by_default() -> None:
    excerpt, start, end = _source_excerpt(
        "ebben a szovegreszben nincs pontos idezet",
        "masik idezet",
        None,
        None,
    )

    assert excerpt is None
    assert start is None
    assert end is None


def test_report_source_expands_document_chunk_and_excerpt_details() -> None:
    document_id = uuid4()
    page_id = uuid4()
    chunk_id = uuid4()
    source_reference = SourceReferenceModel(
        id=uuid4(),
        case_id=uuid4(),
        document_id=document_id,
        page_id=page_id,
        chunk_id=chunk_id,
        page_number=3,
        quote_text="fontos idezet",
        quote_char_start=6,
        quote_char_end=18,
        citation_label="irat.txt, chunk 2",
        source_kind="chunk_quote",
    )
    document = DocumentModel(
        id=document_id,
        case_id=source_reference.case_id,
        original_filename="irat.txt",
        stored_path="/data/immutable/irat.txt",
        mime_type="text/plain",
        file_size_bytes=100,
        sha256_hash="b" * 64,
        imported_by_user_id=uuid4(),
        processing_status="processed",
        lifecycle_status="excluded",
    )
    page = DocumentPageModel(
        id=page_id,
        case_id=source_reference.case_id,
        document_id=document_id,
        page_number=3,
        text_source="native",
        ocr_used=False,
        text_char_count=11,
    )
    chunk = DocumentChunkModel(
        id=chunk_id,
        case_id=source_reference.case_id,
        document_id=document_id,
        page_start=3,
        page_end=3,
        chunk_index=2,
        char_start=100,
        char_end=124,
        chunking_strategy="char_window",
        chunker_version="char_window_v1",
    )
    page._text_store_text = "oldal szoveg"
    chunk._text_store_text = "eleje fontos idezet vege"
    report_source = _report_source_from_reference(
        FakeDb(
            {
                (DocumentModel, document_id): document,
                (DocumentPageModel, page_id): page,
                (DocumentChunkModel, chunk_id): chunk,
            }
        ),
        source_reference,
        support_type="direct",
        relevance_rank=1,
        source_link_id=uuid4(),
        source_link_type="entity_mention",
    )

    assert report_source.document_filename == "irat.txt"
    assert report_source.document_sha256_hash == "b" * 64
    assert report_source.document_lifecycle_status == "excluded"
    assert report_source.chunk_index == 2
    assert report_source.chunk_char_start == 100
    assert report_source.page_text_source == "native"
    assert report_source.source_link_type == "entity_mention"
    assert report_source.source_link_id is not None
    assert report_source.source_text_excerpt == "eleje fontos idezet vege"
