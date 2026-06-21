from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import app.api.v1.rag as rag_api
from app.models.rag_answer import RagAnswerModel
from app.models.document import DocumentChunkModel
from app.schemas.rag import RagAnswerPayload, RagQueryRequest, RagSaveAnswerRequest
from app.services.document_collections import ScopeResolution
from app.services.rag import (
    RAG_QUERY_SYSTEM_PROMPT,
    RagNotFoundError,
    RagValidationError,
    build_rag_query_user_prompt,
    build_rag_synthesis_user_prompt,
    parse_rag_answer_payload,
    parse_rag_llm_json_object,
    _generate_rag_answer,
    _group_retrieved_chunks_by_document,
    _build_used_sources,
    _placeholder_answer,
    _select_rag_source_chunks,
    _detail,
    _list_item,
)
from app.services.analysis_module_common import RetrievedChunk


def test_rag_query_request_requires_document_id_for_document_scope() -> None:
    with pytest.raises(ValidationError):
        RagQueryRequest(question="Mit tudunk erről?", source_mode="document")


def test_rag_query_request_rejects_collection_id_outside_collection_scope() -> None:
    with pytest.raises(ValidationError):
        RagQueryRequest(question="Mit tudunk erről?", source_mode="case", collection_id=uuid4())


def test_rag_query_request_accepts_collection_scope() -> None:
    collection_id = uuid4()

    payload = RagQueryRequest(question="Mit tudunk erről?", source_mode="collection", collection_id=collection_id)

    assert payload.collection_id == collection_id
    assert payload.answer_mode == "detailed"
    assert payload.retrieval_strategy == "hybrid"
    assert payload.max_chunks == 45


def test_rag_query_request_caps_max_chunks() -> None:
    with pytest.raises(ValidationError):
        RagQueryRequest(question="Mit tudunk erről?", max_chunks=91)


def test_rag_query_request_rejects_retired_answer_modes() -> None:
    with pytest.raises(ValidationError):
        RagQueryRequest(question="Mit tudunk erről?", answer_mode="source_focused")


def test_rag_api_maps_query_not_found(monkeypatch) -> None:
    def _raise_not_found(db, case_id, payload):
        raise RagNotFoundError("missing")

    monkeypatch.setattr(rag_api, "run_rag_query", _raise_not_found)

    with pytest.raises(HTTPException) as exc:
        rag_api.post_rag_query(uuid4(), RagQueryRequest(question="Kérdés"), db=object())

    assert exc.value.status_code == 404


def test_rag_api_maps_save_validation(monkeypatch) -> None:
    def _raise_validation(db, case_id, run_id, payload):
        raise RagValidationError("bad run")

    monkeypatch.setattr(rag_api, "save_rag_answer", _raise_validation)

    with pytest.raises(HTTPException) as exc:
        rag_api.post_rag_save_answer(uuid4(), uuid4(), RagSaveAnswerRequest(), db=object())

    assert exc.value.status_code == 400


def test_rag_saved_answer_list_item_uses_source_scope_summary() -> None:
    answer = _answer_model(source_scope_json={"source_mode": "collection"}, used_sources_json=[{"chunk_id": str(uuid4())}])

    item = _list_item(answer)

    assert item.source_mode == "collection"
    assert item.source_label == "Iratgyűjtemény"
    assert item.used_source_count == 1


def test_rag_saved_answer_detail_preserves_payloads() -> None:
    source_scope = {"source_mode": "case", "resolved_document_count": 2}
    used_sources = [{"quote_preview": "idézet"}]
    retrieval_metadata = {"retrieval_strategy": "hybrid", "source_summary": "Forrásösszegzés."}
    answer = _answer_model(
        source_scope_json=source_scope,
        used_sources_json=used_sources,
        retrieval_metadata_json=retrieval_metadata,
    )

    detail = _detail(answer)

    assert detail.source_scope == source_scope
    assert detail.used_sources == used_sources
    assert detail.retrieval_metadata == retrieval_metadata
    assert detail.source_summary == "Forrásösszegzés."


def test_rag_api_list_wraps_service_response(monkeypatch) -> None:
    item = SimpleNamespace(
        id=uuid4(),
        title="Mentett válasz",
        question="Kérdés",
        answer_mode="detailed",
        source_mode="case",
        source_label="Teljes ügy",
        created_at=datetime.now(UTC),
        used_source_count=0,
    )
    monkeypatch.setattr(rag_api, "list_rag_answers", lambda db, case_id: [item])

    response = rag_api.get_rag_answers(uuid4(), db=object())

    assert response.data[0].title == "Mentett válasz"


def test_rag_select_source_chunks_adapts_to_existing_retrieval(monkeypatch) -> None:
    case_id = uuid4()
    document_id = uuid4()
    captured = {}

    def _fake_retrieve(db, received_case_id, payload, *, document_ids=None):
        captured["case_id"] = received_case_id
        captured["payload"] = payload
        captured["document_ids"] = document_ids
        return []

    monkeypatch.setattr("app.services.rag.retrieve_source_scope_chunks", _fake_retrieve)
    resolution = ScopeResolution(
        source_mode="documents",
        requested_document_ids=[document_id],
        requested_collection_ids=[],
        resolved_document_ids=[document_id],
        inactive_document_count=0,
        duplicate_membership_count=0,
        warnings=[],
    )

    chunks = _select_rag_source_chunks(
        db=object(),
        case_id=case_id,
        payload=RagQueryRequest(question="Alfonzo Garcio", source_mode="case", retrieval_strategy="keyword"),
        resolution=resolution,
    )

    assert chunks == []
    assert captured["case_id"] == case_id
    assert captured["document_ids"] == [document_id]
    assert captured["payload"].query == "Alfonzo Garcio"
    assert captured["payload"].source_mode == "case"
    assert captured["payload"].document_ids == [document_id]


def test_rag_placeholder_answer_distinguishes_missing_and_selected_sources() -> None:
    empty = _placeholder_answer(RagQueryRequest(question="Kérdés"), [])
    selected = _placeholder_answer(RagQueryRequest(question="Kérdés"), [_retrieved_chunk("chunk_1", "forrás")])

    assert empty.insufficient_source is True
    assert "nem található" in empty.answer_text
    assert selected.insufficient_source is True
    assert "találtam forrásszövegeket" in selected.answer_text


def test_rag_build_used_sources_reads_chunk_text(monkeypatch) -> None:
    retrieved = _retrieved_chunk("chunk_1", "Ez egy hosszabb forrásszöveg.")
    monkeypatch.setattr("app.services.rag.read_chunk_text_from_store", lambda db, chunk: "Ez egy hosszabb forrásszöveg.")

    sources = _build_used_sources(object(), [retrieved])

    assert sources[0].document_id == retrieved.chunk.document_id
    assert sources[0].document_filename == "irat.txt"
    assert sources[0].page_number == 3
    assert sources[0].chunk_index == 2
    assert sources[0].quote_preview == "Ez egy hosszabb forrásszöveg."
    assert sources[0].retrieval_match_type == "keyword"


def test_build_rag_query_user_prompt_includes_labeled_sources(monkeypatch) -> None:
    retrieved = _retrieved_chunk("chunk_1", "Forrásszöveg.")
    monkeypatch.setattr("app.services.rag.read_chunk_text_from_store", lambda db, chunk: "Forrásszöveg.")

    prompt = build_rag_query_user_prompt(object(), "Mi történt?", "detailed", [retrieved])

    assert "QUERY:\nMi történt?" in prompt
    assert "ANSWER_MODE:\ndetailed" in prompt
    assert "[source_1]" in prompt
    assert "document: irat.txt" in prompt
    assert "Forrásszöveg." in prompt
    assert "FELADAT:" not in prompt


def test_build_rag_synthesis_user_prompt_uses_document_answers() -> None:
    prompt = build_rag_synthesis_user_prompt(
        "Mi történt?",
        "detailed",
        [
            ("A.pdf", _answer_payload("A válasz.", source_summary="A forrás.", insufficient_source=False)),
            ("B.pdf", _answer_payload("B válasz.", source_summary="", insufficient_source=True)),
        ],
    )

    assert "[document_answer_1]" in prompt
    assert "document: A.pdf" in prompt
    assert "insufficient_source: false" in prompt
    assert "answer_text:\nA válasz." in prompt
    assert "[document_answer_2]" in prompt
    assert "insufficient_source: true" in prompt


def test_group_retrieved_chunks_by_document_orders_sources() -> None:
    first_document_id = uuid4()
    second_document_id = uuid4()
    chunks = [
        _retrieved_chunk("chunk_1", "Második irat.", document_id=second_document_id, document_name="B.pdf", page_start=1, chunk_index=0),
        _retrieved_chunk("chunk_2", "Első irat második.", document_id=first_document_id, document_name="A.pdf", page_start=2, chunk_index=1),
        _retrieved_chunk("chunk_3", "Első irat első.", document_id=first_document_id, document_name="A.pdf", page_start=1, chunk_index=0),
    ]

    groups = _group_retrieved_chunks_by_document(chunks)

    assert [[retrieved.label for retrieved in group] for group in groups] == [["chunk_3", "chunk_2"], ["chunk_1"]]


def test_rag_system_prompt_preserves_source_certainty_rules() -> None:
    assert "Ne egeszitsd ki a tortenetet emlekezetbol" in RAG_QUERY_SYSTEM_PROMPT
    assert "SOURCE csak feltetelezeskent" in RAG_QUERY_SYSTEM_PROMPT
    assert "ki vallott be valamit" in RAG_QUERY_SYSTEM_PROMPT
    assert "orizze meg a SOURCE bizonyossagi szintjet" in RAG_QUERY_SYSTEM_PROMPT


def test_parse_rag_answer_payload_requires_boolean_insufficient_source() -> None:
    with pytest.raises(RagValidationError):
        parse_rag_answer_payload(
            {"answer_text": "Válasz.", "source_summary": "Forrás.", "insufficient_source": "false"},
            "detailed",
        )


def test_parse_rag_answer_payload_accepts_minimal_json() -> None:
    payload = parse_rag_answer_payload(
        {"answer_text": "Válasz.", "source_summary": "Forrás.", "insufficient_source": False},
        "detailed",
    )

    assert payload.answer_text == "Válasz."
    assert payload.source_summary == "Forrás."
    assert payload.insufficient_source is False
    assert payload.answer_mode == "detailed"


def test_parse_rag_answer_payload_drops_overlong_source_summary() -> None:
    payload = parse_rag_answer_payload(
        {"answer_text": "Válasz.", "source_summary": "forrás " * 80, "insufficient_source": False},
        "detailed",
    )

    assert payload.source_summary == ""


def test_parse_rag_llm_json_object_recovers_multiline_string_json() -> None:
    raw = (
        '{"answer_text":"Első mondat.\n'
        'Második mondat „idézett” résszel.",'
        '"source_summary":"Forrásösszegzés source_1 alapján.",'
        '"insufficient_source":false}'
    )

    payload = parse_rag_llm_json_object(raw)

    assert payload["answer_text"] == "Első mondat.\nMásodik mondat „idézett” résszel."
    assert payload["source_summary"] == "Forrásösszegzés source_1 alapján."
    assert payload["insufficient_source"] is False


def test_generate_rag_answer_uses_llm_json(monkeypatch) -> None:
    calls = []

    class _FakeCompletion:
        content = '{"answer_text":"Válasz.","source_summary":"Forrás.","insufficient_source":false}'

    class _FakeProvider:
        def __init__(self, settings):
            self.settings = settings

        def chat_completion(self, model, messages, *, temperature, max_tokens):
            calls.append(messages)
            assert model
            assert messages[0].role == "system"
            assert messages[1].role == "user"
            assert temperature == 0.1
            assert max_tokens is None
            return _FakeCompletion()

    monkeypatch.setattr("app.services.rag.LMStudioNativeProvider", _FakeProvider)
    monkeypatch.setattr("app.services.rag.read_chunk_text_from_store", lambda db, chunk: "Forrásszöveg.")

    answer = _generate_rag_answer(
        object(),
        RagQueryRequest(question="Mi történt?", answer_mode="detailed"),
        [_retrieved_chunk("chunk_1", "Forrásszöveg.")],
    )

    assert answer.answer_text == "Válasz."
    assert answer.insufficient_source is False
    assert len(calls) == 1


def test_generate_rag_answer_uses_document_answers_then_synthesis(monkeypatch) -> None:
    first_document_id = uuid4()
    second_document_id = uuid4()
    completions = [
        '{"answer_text":"Az első irat válasza.","source_summary":"A.pdf","insufficient_source":false}',
        '{"answer_text":"A második irat válasza.","source_summary":"B.pdf","insufficient_source":false}',
        '{"answer_text":"Összesített válasz.","source_summary":"A.pdf és B.pdf","insufficient_source":false}',
    ]
    captured_user_prompts = []

    class _FakeCompletion:
        def __init__(self, content):
            self.content = content

    class _FakeProvider:
        def __init__(self, settings):
            self.settings = settings

        def chat_completion(self, model, messages, *, temperature, max_tokens):
            captured_user_prompts.append(messages[1].content)
            return _FakeCompletion(completions.pop(0))

    monkeypatch.setattr("app.services.rag.LMStudioNativeProvider", _FakeProvider)
    monkeypatch.setattr("app.services.rag.read_chunk_text_from_store", lambda db, chunk: getattr(chunk, "_text_store_text", "Forrás."))

    answer = _generate_rag_answer(
        object(),
        RagQueryRequest(question="Mi történt?", answer_mode="detailed"),
        [
            _retrieved_chunk("chunk_1", "B forrás.", document_id=second_document_id, document_name="B.pdf", page_start=1, chunk_index=0),
            _retrieved_chunk("chunk_2", "A forrás.", document_id=first_document_id, document_name="A.pdf", page_start=1, chunk_index=0),
        ],
    )

    assert answer.answer_text == "Összesített válasz."
    assert len(captured_user_prompts) == 3
    assert "document: A.pdf" in captured_user_prompts[0]
    assert "document: B.pdf" in captured_user_prompts[1]
    assert "[document_answer_1]" in captured_user_prompts[2]


def _answer_model(
    *,
    source_scope_json: dict | None = None,
    used_sources_json: list | None = None,
    retrieval_metadata_json: dict | None = None,
) -> RagAnswerModel:
    return RagAnswerModel(
        id=uuid4(),
        case_id=uuid4(),
        analysis_run_id=uuid4(),
        title="Mentett válasz",
        question="Mit tudunk?",
        answer_text="Válasz.",
        answer_mode="detailed",
        source_scope_json=source_scope_json or {"source_mode": "case"},
        used_sources_json=used_sources_json or [],
        retrieval_metadata_json=retrieval_metadata_json or {},
        model_name="qwen/qwen3.5-9b",
        note=None,
        created_at=datetime.now(UTC),
        created_by_user_id=uuid4(),
    )


def _answer_payload(answer_text: str, *, source_summary: str, insufficient_source: bool) -> RagAnswerPayload:
    return RagAnswerPayload(
        answer_text=answer_text,
        source_summary=source_summary,
        insufficient_source=insufficient_source,
        answer_mode="detailed",
    )


def _retrieved_chunk(
    label: str,
    text: str,
    *,
    document_id=None,
    document_name: str = "irat.txt",
    page_start: int = 3,
    chunk_index: int = 2,
) -> RetrievedChunk:
    chunk = DocumentChunkModel(
        id=uuid4(),
        case_id=uuid4(),
        document_id=document_id or uuid4(),
        page_start=page_start,
        page_end=page_start,
        chunk_index=chunk_index,
        char_start=0,
        char_end=len(text),
        token_count=10,
        chunking_strategy="char_window_v2",
        chunker_version="1",
        version_no=1,
        is_current=True,
    )
    chunk._text_store_text = text
    return RetrievedChunk(
        label=label,
        document_name=document_name,
        chunk=chunk,
        retrieval_score=0.7,
        match_type="keyword",
    )
