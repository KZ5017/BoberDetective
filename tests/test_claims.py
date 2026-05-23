from uuid import uuid4

import pytest

from app.models.claim import ClaimModel
from app.services.claims import ClaimValidationError, _review_status_for_action, create_claim_with_source, merge_claim


class _FakeDb:
    def get(self, model, key):
        return None


def test_create_claim_requires_non_empty_text() -> None:
    with pytest.raises(ClaimValidationError):
        create_claim_with_source(
            _FakeDb(),
            case_id=uuid4(),
            claim_text=" ",
            source_reference_id=uuid4(),
            analysis_run_id=uuid4(),
        )


def test_create_claim_requires_analysis_run() -> None:
    with pytest.raises(ClaimValidationError):
        create_claim_with_source(
            _FakeDb(),
            case_id=uuid4(),
            claim_text="A forras allit valamit.",
            source_reference_id=uuid4(),
            analysis_run_id=uuid4(),
        )


def test_merge_claim_rejects_same_source_and_target() -> None:
    claim_id = uuid4()
    with pytest.raises(ClaimValidationError):
        merge_claim(
            _FakeDb(),
            case_id=uuid4(),
            source_claim_id=claim_id,
            target_claim_id=claim_id,
        )


def test_merge_claim_rejects_corrected_target() -> None:
    case_id = uuid4()
    source = ClaimModel(
        id=uuid4(),
        case_id=case_id,
        claim_type="document_fact",
        claim_title="Forrás szerinti állítás",
        claim_text="A forrás állít valamit.",
        created_by_analysis_run_id=uuid4(),
        review_status="needs_review",
    )
    target = ClaimModel(
        id=uuid4(),
        case_id=case_id,
        claim_type="document_fact",
        claim_title="Korábbi állítás",
        claim_text="Korábban javított állítás.",
        created_by_analysis_run_id=uuid4(),
        review_status="corrected",
    )

    class _Db:
        def get(self, model, key):
            return {source.id: source, target.id: target}.get(key)

    with pytest.raises(ClaimValidationError, match="Corrected claims cannot be merge targets"):
        merge_claim(
            _Db(),
            case_id=case_id,
            source_claim_id=source.id,
            target_claim_id=target.id,
        )


def test_merge_claim_rejects_source_invalid_source() -> None:
    case_id = uuid4()
    source = ClaimModel(
        id=uuid4(),
        case_id=case_id,
        claim_type="document_fact",
        claim_title="Forrás nélküli állítás",
        claim_text="Nincs érvényes forrása.",
        created_by_analysis_run_id=uuid4(),
        source_validation_status="source_invalid",
        review_status="needs_review",
    )
    target = ClaimModel(
        id=uuid4(),
        case_id=case_id,
        claim_type="document_fact",
        claim_title="Célállítás",
        claim_text="Érvényes cél.",
        created_by_analysis_run_id=uuid4(),
        source_validation_status="source_valid",
        review_status="needs_review",
    )

    class _Db:
        def get(self, model, key):
            return {source.id: source, target.id: target}.get(key)

    with pytest.raises(ClaimValidationError, match="Claims without valid sources cannot be merged"):
        merge_claim(
            _Db(),
            case_id=case_id,
            source_claim_id=source.id,
            target_claim_id=target.id,
        )


def test_claim_review_status_mapping() -> None:
    assert _review_status_for_action("verify", "needs_review") == "verified"
    assert _review_status_for_action("reject", "needs_review") == "rejected"
    assert _review_status_for_action("mark_needs_review", "verified") == "needs_review"
    assert _review_status_for_action("comment", "needs_review") is None
