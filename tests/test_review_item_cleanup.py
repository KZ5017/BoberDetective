from app.services.review_item_cleanup import _cleanup_allowed, _text_update_allowed


def test_review_item_cleanup_allowed_for_corrected_or_source_invalid() -> None:
    assert _cleanup_allowed("corrected", "source_valid")
    assert _cleanup_allowed("needs_review", "source_invalid")
    assert _cleanup_allowed("corrected", "source_invalid")


def test_review_item_cleanup_rejects_active_valid_items() -> None:
    assert not _cleanup_allowed("needs_review", "source_valid")
    assert not _cleanup_allowed("verified", "source_valid")
    assert not _cleanup_allowed("rejected", "source_valid")


def test_review_item_text_update_allowed_only_for_source_valid_non_corrected_items() -> None:
    assert _text_update_allowed("needs_review", "source_valid")
    assert _text_update_allowed("verified", "source_valid")
    assert _text_update_allowed("rejected", "source_valid")
    assert not _text_update_allowed("corrected", "source_valid")
    assert not _text_update_allowed("needs_review", "source_invalid")
