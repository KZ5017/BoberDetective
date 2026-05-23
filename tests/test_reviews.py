import pytest

from app.services.reviews import ReviewValidationError, ensure_review_status_transition, review_status_for_action


def test_shared_review_status_mapping() -> None:
    assert review_status_for_action("verify", "needs_review") == "verified"
    assert review_status_for_action("reject", "needs_review") == "rejected"
    assert review_status_for_action("mark_needs_review", "verified") == "needs_review"
    assert review_status_for_action("comment", "needs_review") is None


def test_shared_review_status_rejects_unknown_action() -> None:
    with pytest.raises(ReviewValidationError):
        review_status_for_action("publish", "needs_review")


def test_review_status_transition_rejects_same_status_action() -> None:
    with pytest.raises(ReviewValidationError):
        ensure_review_status_transition("verify", "verified", "verified")


def test_review_status_transition_allows_comment_no_status_change() -> None:
    ensure_review_status_transition("comment", "verified", None)
