from app.services.review_report import _build_counts


def test_review_report_counts_known_statuses() -> None:
    counts = _build_counts(["needs_review", "needs_review", "verified", "rejected", "new", "corrected"])

    assert counts.total == 6
    assert counts.needs_review == 2
    assert counts.verified == 1
    assert counts.rejected == 1
    assert counts.new == 1
    assert counts.corrected == 1


def test_review_report_counts_missing_statuses_as_zero() -> None:
    counts = _build_counts(["verified"])

    assert counts.total == 1
    assert counts.needs_review == 0
    assert counts.verified == 1
    assert counts.rejected == 0
