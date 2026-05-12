from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.schemas.review_report import ReviewReportFilters, ReviewReportItem
from app.services.review_report import ReviewReportValidationError, _build_counts, _filter_items


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
    counts = _build_counts(["needs_review", "needs_review", "verified", "rejected", "new", "corrected"])

    assert counts.total == 6
    assert counts.needs_review == 2
    assert counts.verified == 1
    assert counts.rejected == 1
    assert counts.new == 1
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
        _item("entity", "needs_review", "source_valid"),
        _item("event", "verified", "source_valid"),
        _item("event", "needs_review", "source_invalid"),
    ]

    filtered = _filter_items(
        items,
        ReviewReportFilters(
            object_types=["entity", "event"],
            review_statuses=["needs_review"],
            source_validation_statuses=["source_valid"],
        ),
    )

    assert [(item.object_type, item.review_status) for item in filtered] == [("entity", "needs_review")]


def test_review_report_filters_reject_unknown_values() -> None:
    with pytest.raises(ReviewReportValidationError):
        _filter_items([_item("claim", "needs_review", "source_valid")], ReviewReportFilters(object_types=["export"]))
