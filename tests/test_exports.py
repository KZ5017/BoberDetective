from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.schemas.export import ExportCreate
from app.schemas.review_report import CaseReviewReport, ReviewReportItem, ReviewReportSource
from app.services.exports import ExportValidationError, _build_html_export, _filter_report_items, _review_status_for_action


def _item(review_status: str, source_validation_status: str = "source_valid", has_source: bool = True) -> ReviewReportItem:
    sources = []
    if has_source:
        sources.append(
            ReviewReportSource(
                source_reference_id=uuid4(),
                document_id=uuid4(),
                document_filename="irat.txt",
                document_sha256_hash="a" * 64,
                page_id=None,
                chunk_id=uuid4(),
                page_number=1,
                chunk_index=0,
                citation_label="doc.txt, chunk 0",
                quote_text="forras idezet",
                source_text_excerpt="forras idezet",
                source_kind="chunk_quote",
                support_type="direct",
                relevance_rank=0,
            )
        )
    return ReviewReportItem(
        object_type="claim",
        object_id=uuid4(),
        title="Allitas",
        body_text="Allitas",
        subtype="document_fact",
        review_status=review_status,
        source_validation_status=source_validation_status,
        created_by_analysis_run_id=uuid4(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        sources=sources,
        reviews=[],
    )


def test_export_filter_verified_only_and_source_valid() -> None:
    items = [
        _item("verified"),
        _item("needs_review"),
        _item("verified", source_validation_status="source_invalid"),
        _item("verified", has_source=False),
    ]

    filtered = _filter_report_items(items, "verified_only", require_source_valid=True)

    assert len(filtered) == 1
    assert filtered[0].review_status == "verified"


def test_export_filter_all_can_include_needs_review_when_requested() -> None:
    items = [_item("needs_review"), _item("verified")]

    filtered = _filter_report_items(items, "all", require_source_valid=True)

    assert [item.review_status for item in filtered] == ["needs_review", "verified"]


def test_export_review_status_mapping() -> None:
    assert _review_status_for_action("verify", "needs_review") == "verified"
    assert _review_status_for_action("reject", "needs_review") == "rejected"
    assert _review_status_for_action("mark_needs_review", "verified") == "needs_review"
    assert _review_status_for_action("comment", "needs_review") is None


def test_export_review_status_rejects_unknown_action() -> None:
    with pytest.raises(ExportValidationError):
        _review_status_for_action("publish", "needs_review")


def test_html_export_escapes_item_and_source_text() -> None:
    malicious = '<script>alert("x")</script>'
    item = _item("needs_review")
    item.title = malicious
    item.body_text = malicious
    item.sources[0].quote_text = malicious
    report = CaseReviewReport(
        case_id=uuid4(),
        counts={
            "total": 1,
            "needs_review": 1,
            "verified": 0,
            "rejected": 0,
            "corrected": 0,
            "new": 0,
        },
        items=[item],
    )

    html = _build_html_export(
        report,
        [item],
        ExportCreate(export_type="html", export_scope="review_report"),
    )

    assert malicious not in html
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in html
    assert "irat.txt" in html
    assert "Excerpt chars" in html
