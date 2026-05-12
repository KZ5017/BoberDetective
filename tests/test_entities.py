from uuid import uuid4

import pytest

from app.services.entities import EntityValidationError, _review_status_for_action, create_entity_with_mention


class _FakeDb:
    def get(self, model, key):
        return None


def test_create_entity_requires_canonical_name() -> None:
    with pytest.raises(EntityValidationError):
        create_entity_with_mention(
            _FakeDb(),
            case_id=uuid4(),
            entity_type="person",
            canonical_name=" ",
            normalized_value=None,
            description=None,
            surface_text="Kovacs Anna",
            source_reference_id=uuid4(),
            analysis_run_id=uuid4(),
        )


def test_create_entity_requires_analysis_run() -> None:
    with pytest.raises(EntityValidationError):
        create_entity_with_mention(
            _FakeDb(),
            case_id=uuid4(),
            entity_type="person",
            canonical_name="Kovacs Anna",
            normalized_value=None,
            description=None,
            surface_text="Kovacs Anna",
            source_reference_id=uuid4(),
            analysis_run_id=uuid4(),
        )


def test_entity_review_status_mapping() -> None:
    assert _review_status_for_action("verify", "needs_review") == "verified"
    assert _review_status_for_action("reject", "needs_review") == "rejected"
    assert _review_status_for_action("mark_needs_review", "verified") == "needs_review"
    assert _review_status_for_action("comment", "needs_review") is None


def test_entity_review_status_rejects_unknown_action() -> None:
    with pytest.raises(EntityValidationError):
        _review_status_for_action("publish", "needs_review")
