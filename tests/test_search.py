from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.v1 import search as search_api
from app.schemas.search import HybridSearchRequest, KeywordSearchRequest, SearchFilters
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


def test_hybrid_search_api_passes_page_range_to_semantic_branch(monkeypatch) -> None:
    captured = {}

    monkeypatch.setattr(search_api, "keyword_search", lambda *args, **kwargs: [])
    monkeypatch.setattr(search_api, "_semantic_filter_document_ids", lambda *args, **kwargs: [])

    def fake_semantic_chunk_search(db, case_id, query, limit, *, document_ids=None, page_start=None, page_end=None):
        captured["document_ids"] = document_ids
        captured["page_start"] = page_start
        captured["page_end"] = page_end
        return []

    monkeypatch.setattr(search_api, "semantic_chunk_search", fake_semantic_chunk_search)

    search_api.post_hybrid_search(
        case_id=uuid4(),
        payload=HybridSearchRequest(
            query="kerdes",
            retrieval_strategy="semantic",
            filters=SearchFilters(page_start=12, page_end=18),
        ),
        db=object(),
    )

    assert captured == {"document_ids": [], "page_start": 12, "page_end": 18}
