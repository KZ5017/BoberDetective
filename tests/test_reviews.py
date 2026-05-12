import pytest

from app.services.reviews import ReviewValidationError, review_status_for_action


def test_shared_review_status_mapping() -> None:
    assert review_status_for_action("verify", "needs_review") == "verified"
    assert review_status_for_action("reject", "needs_review") == "rejected"
    assert review_status_for_action("mark_needs_review", "verified") == "needs_review"
    assert review_status_for_action("comment", "needs_review") is None


def test_shared_review_status_rejects_unknown_action() -> None:
    with pytest.raises(ReviewValidationError):
        review_status_for_action("publish", "needs_review")
