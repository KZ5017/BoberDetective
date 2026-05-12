import pytest
from pydantic import ValidationError

from app.schemas.search import KeywordSearchRequest
from app.services.search import _make_prefix_tsquery, _make_quote


def test_keyword_search_request_rejects_empty_query() -> None:
    with pytest.raises(ValidationError):
        KeywordSearchRequest(query="")


def test_keyword_search_request_rejects_invalid_target() -> None:
    with pytest.raises(ValidationError):
        KeywordSearchRequest(query="telefon", target="database")


def test_keyword_quote_centers_first_matching_term() -> None:
    quote = _make_quote("alpha beta gamma delta epsilon", "gamma", max_chars=14)

    assert "gamma" in quote
    assert quote.endswith("...")


def test_keyword_quote_is_plain_text_not_markup() -> None:
    quote = _make_quote("<b>telefon</b> hivas", "telefon", max_chars=40)

    assert quote == "<b>telefon</b> hivas"


def test_keyword_prefix_tsquery_uses_sanitized_prefix_terms() -> None:
    assert _make_prefix_tsquery("telefonhivas kapu") == "telefonhivas:* & kapu:*"


def test_keyword_prefix_tsquery_strips_tsquery_operators() -> None:
    assert _make_prefix_tsquery("telefon:* | kapu") == "telefon:* & kapu:*"
