from uuid import uuid4
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.v1 import search as search_api
from app.models.document import DocumentChunkModel, DocumentPageModel, DocumentSearchEntryModel
from app.schemas.search import HybridSearchRequest, KeywordSearchRequest, SearchFilters
from app.services import search as search_service
from app.services.search import _make_prefix_tsquery, _make_quote, _search_chunks, _search_pages


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


def test_keyword_search_returns_empty_for_query_without_terms() -> None:
    assert search_service.keyword_search(object(), uuid4(), KeywordSearchRequest(query="???")) == []


def test_chunk_keyword_search_uses_search_entry_and_text_store_quote(monkeypatch) -> None:
    case_id = uuid4()
    document_id = uuid4()
    chunk_id = uuid4()
    entry = DocumentSearchEntryModel(
        case_id=case_id,
        document_id=document_id,
        source_type="chunk",
        chunk_id=chunk_id,
        page_start=2,
        page_end=2,
        chunk_index=3,
        lifecycle_status="active",
        text_hash="a" * 64,
        is_current=True,
    )
    chunk = DocumentChunkModel(
        id=chunk_id,
        case_id=case_id,
        document_id=document_id,
        page_start=2,
        page_end=2,
        chunk_index=3,
        chunking_strategy="char_window_v2",
        chunker_version="2",
        version_no=1,
        is_current=True,
    )
    db = _FakeSearchDb(entry, chunk)
    monkeypatch.setattr(search_service, "read_chunk_text_from_store", lambda db_arg, chunk_arg: "Text-store chunk telefon.")

    hits = _search_chunks(db, case_id, KeywordSearchRequest(query="telefon", include_quotes=True), "telefon")

    assert len(hits) == 1
    assert hits[0].chunk_id == chunk_id
    assert hits[0].quote == "Text-store chunk telefon."


def test_page_keyword_search_uses_search_entry_and_text_store_quote(monkeypatch) -> None:
    case_id = uuid4()
    document_id = uuid4()
    page_id = uuid4()
    entry = DocumentSearchEntryModel(
        case_id=case_id,
        document_id=document_id,
        source_type="page",
        page_id=page_id,
        page_start=5,
        page_end=5,
        lifecycle_status="active",
        text_hash="b" * 64,
        is_current=True,
    )
    page = DocumentPageModel(
        id=page_id,
        case_id=case_id,
        document_id=document_id,
        page_number=5,
        text_source="native",
        ocr_used=False,
        version_no=1,
        is_current=True,
        text_char_count=19,
    )
    db = _FakeSearchDb(entry, page)
    monkeypatch.setattr(search_service, "read_page_text_from_store", lambda db_arg, page_arg: "Text-store oldal telefon.")

    hits = _search_pages(db, case_id, KeywordSearchRequest(query="telefon", include_quotes=True, target="pages"), "telefon")

    assert len(hits) == 1
    assert hits[0].page_id == page_id
    assert hits[0].quote == "Text-store oldal telefon."


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


class _FakeSearchDb:
    def __init__(self, entry, source_object) -> None:
        self.entry = entry
        self.source_object = source_object

    def execute(self, statement):
        _ = statement
        return [SimpleNamespace(DocumentSearchEntryModel=self.entry, original_filename="irat.pdf", score=0.5)]

    def get(self, model, object_id):
        if isinstance(self.source_object, model) and self.source_object.id == object_id:
            return self.source_object
        return None
