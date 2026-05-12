from uuid import uuid4

import pytest

from app.services.summary_items import SummaryItemValidationError, _review_status_for_action, create_summary_item_with_source


class _FakeDb:
    def get(self, model, key):
        return None


def test_create_summary_item_requires_title() -> None:
    with pytest.raises(SummaryItemValidationError):
        create_summary_item_with_source(
            _FakeDb(),
            case_id=uuid4(),
            summary_type="case_overview",
            title=" ",
            body_text="Forrashu osszefoglalo.",
            source_reference_id=uuid4(),
            analysis_run_id=uuid4(),
        )


def test_create_summary_item_requires_body_text() -> None:
    with pytest.raises(SummaryItemValidationError):
        create_summary_item_with_source(
            _FakeDb(),
            case_id=uuid4(),
            summary_type="case_overview",
            title="Rovid cim",
            body_text=" ",
            source_reference_id=uuid4(),
            analysis_run_id=uuid4(),
        )


def test_create_summary_item_requires_analysis_run() -> None:
    with pytest.raises(SummaryItemValidationError):
        create_summary_item_with_source(
            _FakeDb(),
            case_id=uuid4(),
            summary_type="case_overview",
            title="Rovid cim",
            body_text="Forrashu osszefoglalo.",
            source_reference_id=uuid4(),
            analysis_run_id=uuid4(),
        )


def test_summary_item_review_status_mapping() -> None:
    assert _review_status_for_action("verify", "needs_review") == "verified"
    assert _review_status_for_action("reject", "needs_review") == "rejected"
    assert _review_status_for_action("mark_needs_review", "verified") == "needs_review"
    assert _review_status_for_action("comment", "needs_review") is None


def test_summary_item_review_status_rejects_unknown_action() -> None:
    with pytest.raises(SummaryItemValidationError):
        _review_status_for_action("publish", "needs_review")
