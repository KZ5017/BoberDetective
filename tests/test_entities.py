from uuid import uuid4

import pytest

from app.models.entity import EntityModel
from app.services.entities import (
    EntityNotFoundError,
    EntityValidationError,
    _find_existing_entity,
    _review_status_for_action,
    create_entity_with_mention,
    detach_entity_mention,
    merge_entity,
)


class _FakeDb:
    def get(self, model, key):
        return None


class _FakeScalarRows:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self._rows


class _FakeQueryDb:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, statement):
        return _FakeScalarRows(self._rows)


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


def test_merge_entity_rejects_same_source_and_target() -> None:
    entity_id = uuid4()
    with pytest.raises(EntityValidationError):
        merge_entity(
            _FakeDb(),
            case_id=uuid4(),
            source_entity_id=entity_id,
            target_entity_id=entity_id,
        )


def test_detach_entity_mention_requires_existing_entity() -> None:
    with pytest.raises(EntityNotFoundError):
        detach_entity_mention(
            _FakeDb(),
            case_id=uuid4(),
            entity_id=uuid4(),
            mention_id=uuid4(),
        )


def test_find_existing_entity_matches_same_canonical_name() -> None:
    entity = EntityModel(
        id=uuid4(),
        case_id=uuid4(),
        entity_type="person",
        canonical_name="Dupin",
        normalized_value=None,
        created_by_analysis_run_id=uuid4(),
        review_status="needs_review",
    )

    existing = _find_existing_entity(
        _FakeQueryDb([entity]),
        entity.case_id,
        "person",
        " dupin ",
        None,
    )

    assert existing == entity


def test_find_existing_person_entity_does_not_guess_longer_name_alias() -> None:
    entity = EntityModel(
        id=uuid4(),
        case_id=uuid4(),
        entity_type="person",
        canonical_name="C. Auguste Dupin",
        normalized_value=None,
        created_by_analysis_run_id=uuid4(),
        review_status="needs_review",
    )

    existing = _find_existing_entity(
        _FakeQueryDb([entity]),
        entity.case_id,
        "person",
        "Dupin",
        None,
    )

    assert existing is None


def test_entity_review_status_mapping() -> None:
    assert _review_status_for_action("verify", "needs_review") == "verified"
    assert _review_status_for_action("reject", "needs_review") == "rejected"
    assert _review_status_for_action("mark_needs_review", "verified") == "needs_review"
    assert _review_status_for_action("comment", "needs_review") is None


def test_entity_review_status_rejects_unknown_action() -> None:
    with pytest.raises(EntityValidationError):
        _review_status_for_action("publish", "needs_review")
