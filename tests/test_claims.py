from uuid import uuid4

import pytest

from app.services.claims import ClaimValidationError, _review_status_for_action, create_claim_with_source


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


def test_claim_review_status_mapping() -> None:
    assert _review_status_for_action("verify", "needs_review") == "verified"
    assert _review_status_for_action("reject", "needs_review") == "rejected"
    assert _review_status_for_action("mark_needs_review", "verified") == "needs_review"
    assert _review_status_for_action("comment", "needs_review") is None
