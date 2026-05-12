from uuid import uuid4

import pytest

from app.services.events import EventValidationError, _review_status_for_action, create_event_with_source


class _FakeDb:
    def get(self, model, key):
        return None


def test_create_event_requires_non_empty_title() -> None:
    with pytest.raises(EventValidationError):
        create_event_with_source(
            _FakeDb(),
            case_id=uuid4(),
            event_type="call",
            event_title=" ",
            event_description=None,
            event_time_raw=None,
            time_precision="unknown",
            location_text=None,
            source_reference_id=uuid4(),
            analysis_run_id=uuid4(),
        )


def test_create_event_requires_analysis_run() -> None:
    with pytest.raises(EventValidationError):
        create_event_with_source(
            _FakeDb(),
            case_id=uuid4(),
            event_type="call",
            event_title="Telefonhivas",
            event_description=None,
            event_time_raw=None,
            time_precision="unknown",
            location_text=None,
            source_reference_id=uuid4(),
            analysis_run_id=uuid4(),
        )


def test_event_review_status_mapping() -> None:
    assert _review_status_for_action("verify", "needs_review") == "verified"
    assert _review_status_for_action("reject", "needs_review") == "rejected"
    assert _review_status_for_action("mark_needs_review", "verified") == "needs_review"
    assert _review_status_for_action("comment", "needs_review") is None


def test_event_review_status_rejects_unknown_action() -> None:
    with pytest.raises(EventValidationError):
        _review_status_for_action("publish", "needs_review")
