from uuid import uuid4

import pytest

from app.services.events import EventNotFoundError, EventValidationError, _review_status_for_action, create_event_with_source, detach_event_source, merge_event


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


def test_merge_event_rejects_same_source_and_target() -> None:
    event_id = uuid4()
    with pytest.raises(EventValidationError):
        merge_event(
            _FakeDb(),
            case_id=uuid4(),
            source_event_id=event_id,
            target_event_id=event_id,
        )


def test_detach_event_source_requires_existing_event() -> None:
    with pytest.raises(EventNotFoundError):
        detach_event_source(
            _FakeDb(),
            case_id=uuid4(),
            event_id=uuid4(),
            event_source_id=uuid4(),
        )


def test_event_review_status_mapping() -> None:
    assert _review_status_for_action("verify", "needs_review") == "verified"
    assert _review_status_for_action("reject", "needs_review") == "rejected"
    assert _review_status_for_action("mark_needs_review", "verified") == "needs_review"
    assert _review_status_for_action("comment", "needs_review") is None


def test_event_review_status_rejects_unknown_action() -> None:
    with pytest.raises(EventValidationError):
        _review_status_for_action("publish", "needs_review")
