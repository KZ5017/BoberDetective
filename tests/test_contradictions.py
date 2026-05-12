from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.contradiction import ContradictionCandidateCreate, ContradictionSourceCreate
from app.services.contradictions import (
    ContradictionCandidateValidationError,
    _review_status_for_action,
    create_contradiction_candidate,
)


class _FakeDb:
    def get(self, model, key):
        return None


def _sources() -> list[ContradictionSourceCreate]:
    return [
        ContradictionSourceCreate(source_reference_id=uuid4(), side_label="a"),
        ContradictionSourceCreate(source_reference_id=uuid4(), side_label="b"),
    ]


def test_contradiction_create_schema_requires_claim_or_event_pair() -> None:
    with pytest.raises(ValidationError):
        ContradictionCandidateCreate(
            contradiction_type="time_conflict",
            title="Idobeli elteres",
            description="Ket forras mas idopontot emlit.",
            analysis_run_id=uuid4(),
            sources=_sources(),
        )


def test_create_contradiction_candidate_requires_title() -> None:
    with pytest.raises(ContradictionCandidateValidationError):
        create_contradiction_candidate(
            _FakeDb(),
            case_id=uuid4(),
            contradiction_type="time_conflict",
            title=" ",
            description="Ket forras mas idopontot emlit.",
            analysis_run_id=uuid4(),
            claim_id_a=uuid4(),
            claim_id_b=uuid4(),
            sources=_sources(),
        )


def test_create_contradiction_candidate_requires_two_sources() -> None:
    with pytest.raises(ContradictionCandidateValidationError):
        create_contradiction_candidate(
            _FakeDb(),
            case_id=uuid4(),
            contradiction_type="time_conflict",
            title="Idobeli elteres",
            description="Ket forras mas idopontot emlit.",
            analysis_run_id=uuid4(),
            claim_id_a=uuid4(),
            claim_id_b=uuid4(),
            sources=[ContradictionSourceCreate(source_reference_id=uuid4(), side_label="a")],
        )


def test_create_contradiction_candidate_requires_analysis_run() -> None:
    with pytest.raises(ContradictionCandidateValidationError):
        create_contradiction_candidate(
            _FakeDb(),
            case_id=uuid4(),
            contradiction_type="time_conflict",
            title="Idobeli elteres",
            description="Ket forras mas idopontot emlit.",
            analysis_run_id=uuid4(),
            claim_id_a=uuid4(),
            claim_id_b=uuid4(),
            sources=_sources(),
        )


def test_contradiction_candidate_review_status_mapping() -> None:
    assert _review_status_for_action("verify", "needs_review") == "verified"
    assert _review_status_for_action("reject", "needs_review") == "rejected"
    assert _review_status_for_action("mark_needs_review", "verified") == "needs_review"
    assert _review_status_for_action("comment", "needs_review") is None


def test_contradiction_candidate_review_status_rejects_unknown_action() -> None:
    with pytest.raises(ContradictionCandidateValidationError):
        _review_status_for_action("publish", "needs_review")
