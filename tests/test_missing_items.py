from uuid import uuid4

import pytest

from app.models.missing_item import MissingItemCandidateModel
from app.schemas.missing_item import MissingItemSourceCreate
from app.services.missing_items import (
    MissingItemCandidateNotFoundError,
    MissingItemCandidateValidationError,
    _review_status_for_action,
    create_missing_item_candidate,
    detach_missing_item_candidate_source,
    merge_missing_item_candidate,
)


class _FakeDb:
    def get(self, model, key):
        return None


def test_create_missing_item_candidate_requires_referenced_text() -> None:
    with pytest.raises(MissingItemCandidateValidationError):
        create_missing_item_candidate(
            _FakeDb(),
            case_id=uuid4(),
            missing_item_type="attachment",
            referenced_item_text=" ",
            description="A forras mellekletre hivatkozik.",
            analysis_run_id=uuid4(),
            sources=[MissingItemSourceCreate(source_reference_id=uuid4())],
        )


def test_create_missing_item_candidate_requires_description() -> None:
    with pytest.raises(MissingItemCandidateValidationError):
        create_missing_item_candidate(
            _FakeDb(),
            case_id=uuid4(),
            missing_item_type="attachment",
            referenced_item_text="1. szamu melleklet",
            description=" ",
            analysis_run_id=uuid4(),
            sources=[MissingItemSourceCreate(source_reference_id=uuid4())],
        )


def test_create_missing_item_candidate_requires_source() -> None:
    with pytest.raises(MissingItemCandidateValidationError):
        create_missing_item_candidate(
            _FakeDb(),
            case_id=uuid4(),
            missing_item_type="attachment",
            referenced_item_text="1. szamu melleklet",
            description="A forras mellekletre hivatkozik.",
            analysis_run_id=uuid4(),
            sources=[],
        )


def test_create_missing_item_candidate_requires_analysis_run() -> None:
    with pytest.raises(MissingItemCandidateValidationError):
        create_missing_item_candidate(
            _FakeDb(),
            case_id=uuid4(),
            missing_item_type="attachment",
            referenced_item_text="1. szamu melleklet",
            description="A forras mellekletre hivatkozik.",
            analysis_run_id=uuid4(),
            sources=[MissingItemSourceCreate(source_reference_id=uuid4())],
        )


def test_merge_missing_item_candidate_rejects_same_source_and_target() -> None:
    candidate_id = uuid4()
    with pytest.raises(MissingItemCandidateValidationError):
        merge_missing_item_candidate(
            _FakeDb(),
            case_id=uuid4(),
            source_candidate_id=candidate_id,
            target_candidate_id=candidate_id,
        )


def test_merge_missing_item_candidate_rejects_corrected_target() -> None:
    case_id = uuid4()
    source = MissingItemCandidateModel(
        id=uuid4(),
        case_id=case_id,
        missing_item_type="attachment",
        referenced_item_text="1. szamu melleklet",
        description="A forras mellekletre hivatkozik.",
        created_by_analysis_run_id=uuid4(),
        review_status="needs_review",
    )
    target = MissingItemCandidateModel(
        id=uuid4(),
        case_id=case_id,
        missing_item_type="attachment",
        referenced_item_text="1. melleklet",
        description="Korabbi osszevont jelolt.",
        created_by_analysis_run_id=uuid4(),
        review_status="corrected",
    )

    class _Db:
        def get(self, model, key):
            return {source.id: source, target.id: target}.get(key)

    with pytest.raises(
        MissingItemCandidateValidationError,
        match="Corrected missing item candidates cannot be merge targets",
    ):
        merge_missing_item_candidate(
            _Db(),
            case_id=case_id,
            source_candidate_id=source.id,
            target_candidate_id=target.id,
        )


def test_merge_missing_item_candidate_rejects_source_invalid_source() -> None:
    case_id = uuid4()
    source = MissingItemCandidateModel(
        id=uuid4(),
        case_id=case_id,
        missing_item_type="attachment",
        referenced_item_text="1. szamu melleklet",
        description="A forras mellekletre hivatkozik.",
        created_by_analysis_run_id=uuid4(),
        source_validation_status="source_invalid",
        review_status="needs_review",
    )
    target = MissingItemCandidateModel(
        id=uuid4(),
        case_id=case_id,
        missing_item_type="attachment",
        referenced_item_text="1. melleklet",
        description="Masik jelolt.",
        created_by_analysis_run_id=uuid4(),
        source_validation_status="source_valid",
        review_status="needs_review",
    )

    class _Db:
        def get(self, model, key):
            return {source.id: source, target.id: target}.get(key)

    with pytest.raises(
        MissingItemCandidateValidationError,
        match="Missing item candidates without valid sources cannot be merged",
    ):
        merge_missing_item_candidate(
            _Db(),
            case_id=case_id,
            source_candidate_id=source.id,
            target_candidate_id=target.id,
        )


def test_detach_missing_item_candidate_source_requires_existing_candidate() -> None:
    with pytest.raises(MissingItemCandidateNotFoundError):
        detach_missing_item_candidate_source(
            _FakeDb(),
            case_id=uuid4(),
            missing_item_candidate_id=uuid4(),
            source_link_id=uuid4(),
        )


def test_missing_item_candidate_review_status_mapping() -> None:
    assert _review_status_for_action("verify", "needs_review") == "verified"
    assert _review_status_for_action("reject", "needs_review") == "rejected"
    assert _review_status_for_action("mark_needs_review", "verified") == "needs_review"
    assert _review_status_for_action("comment", "needs_review") is None


def test_missing_item_candidate_review_status_rejects_unknown_action() -> None:
    with pytest.raises(MissingItemCandidateValidationError):
        _review_status_for_action("publish", "needs_review")
