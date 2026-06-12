from __future__ import annotations

from uuid import UUID
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.knowledge import KnowledgeDocumentModel
from app.schemas.knowledge import (
    KnowledgeAnswerPayload,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    KnowledgeRetrievalMetadata,
    KnowledgeUsedSource,
)
from app.services.analysis_module_common import AnalysisModuleError, parse_llm_json_object
from app.services.knowledge_indexing import knowledge_collection_name
from app.services.knowledge_retrieval import (
    KnowledgeRetrievalError as KnowledgeQueryError,
    KnowledgeRetrievalValidationError as KnowledgeQueryValidationError,
    KnowledgeRetrievedChunk,
    expand_context_neighbors,
    keyword_knowledge_search,
    merge_hybrid_hits,
    order_retrieved_chunks_for_llm,
    retrieval_candidate_limit,
    semantic_knowledge_search,
)
from app.services.llm import LLMChatMessage, LLMProviderError, LMStudioNativeProvider


KNOWLEDGE_QUERY_SYSTEM_PROMPT = """Forrashu tudasbazis-kerdezo komponens vagy.
A SOURCE az egyetlen igazsagforras.
A QUERY a felhasznalo kerdese vagy utasitasa.
Csak az importalt tudasbazis SOURCE blokkok alapjan valaszolhatsz.
Ne hasznalj kulso tudast, ne potolj hianyzo adatot, ne feltetelezz.
Ha a SOURCE nem ad eleg alapot a valaszhoz, mondd ki roviden.
Ne kezeld a jegyzetet bizonyitekkent vagy ugyiratkent.
Ne futtass parancsot, ne adj autonom vegrehajtasi dontest.

Feladatod, hogy valaszolj a QUERY-re kizarolag a SOURCE alapjan.
A valasz legyen magyar nyelvu.
A valaszmodot az ANSWER_MODE hatarozza meg:
- short: rovid, lenyegre toro valasz.
- detailed: fejtsd ki reszletesen a valaszt, es adj vissza minden erdemi, SOURCE altal alatamasztott informaciot, amely segit a QUERY megvalaszolasaban.

JSON mezok:
- source_summary: legfeljebb egy rovid mondat arrol, mely SOURCE blokkok adjak a valasz alapjat. Ne ismeteld meg az answer_text tartalmat. Ha nem ad hozza hasznos informaciot, legyen ures string.
- insufficient_source: boolean. true, ha a SOURCE nem ad eleg alapot erdemi valaszhoz, kulonben false.
- answer_text: a QUERY-re adott forrashu valasz.

Csak ervenyes JSON objektumot adj vissza.
Ne irj magyarazatot, markdown blokkot vagy JSON-on kivuli szoveget.
A JSON objektumok minden mezőneve dupla idézőjelben legyen.
A JSON stringeken belüli dupla idézőjeleket escape-eld.
Sortorest csak JSON escape-kent hasznalhatsz: \\n.

Elvart JSON forma:
{"source_summary":"...","insufficient_source":false,"answer_text":"..."}
"""

KNOWLEDGE_QUERY_MAX_OUTPUT_TOKENS = None
KNOWLEDGE_SOURCE_SUMMARY_MAX_CHARS = 320


def run_knowledge_query(db: Session, payload: KnowledgeQueryRequest) -> KnowledgeQueryResponse:
    question = payload.question.strip()
    if not question:
        raise KnowledgeQueryValidationError("A kérdés nem lehet üres")
    retrieved_chunks = select_knowledge_source_chunks(db, payload)
    used_sources = _build_used_sources(retrieved_chunks)
    settings = get_settings()
    retrieval_metadata = KnowledgeRetrievalMetadata(
        retrieval_strategy=payload.retrieval_strategy,
        max_chunks=payload.max_chunks,
        selected_chunk_count=len(retrieved_chunks),
        document_count=len({retrieved.document.id for retrieved in retrieved_chunks}),
        embedding_model=settings.llm_embedding_model if payload.retrieval_strategy in {"semantic", "hybrid"} else None,
        collection_name=knowledge_collection_name(settings) if payload.retrieval_strategy in {"semantic", "hybrid"} else None,
    )
    answer = (
        _placeholder_answer(payload)
        if not retrieved_chunks
        else _generate_knowledge_answer(payload, order_retrieved_chunks_for_llm(retrieved_chunks))
    )
    return KnowledgeQueryResponse(
        answer=answer,
        used_sources=used_sources,
        retrieval_metadata=retrieval_metadata,
        can_save=False,
    )


def select_knowledge_source_chunks(db: Session, payload: KnowledgeQueryRequest) -> list[KnowledgeRetrievedChunk]:
    documents = _knowledge_documents(db, payload.document_ids)
    if not documents:
        return []
    if payload.retrieval_strategy == "keyword":
        return keyword_knowledge_search(documents, payload.question, payload.max_chunks)
    candidate_limit = retrieval_candidate_limit(payload.max_chunks)
    if payload.retrieval_strategy == "semantic":
        semantic_hits = semantic_knowledge_search(db, documents, payload.question, candidate_limit)
        return expand_context_neighbors(documents, semantic_hits, payload.max_chunks, query=payload.question)
    keyword_hits = keyword_knowledge_search(documents, payload.question, candidate_limit)
    semantic_hits = semantic_knowledge_search(db, documents, payload.question, candidate_limit)
    hybrid_hits = merge_hybrid_hits(keyword_hits, semantic_hits, candidate_limit, query=payload.question)
    return expand_context_neighbors(documents, hybrid_hits, payload.max_chunks, query=payload.question)


def build_knowledge_query_user_prompt(
    question: str,
    answer_mode: str,
    retrieved_chunks: list[KnowledgeRetrievedChunk],
) -> str:
    return (
        f"QUERY:\n{question.strip()}\n\n"
        f"ANSWER_MODE:\n{answer_mode}\n\n"
        f"SOURCE:\n{_build_knowledge_source_blocks(retrieved_chunks)}"
    )


def parse_knowledge_answer_payload(parsed: dict, answer_mode: str) -> KnowledgeAnswerPayload:
    answer_text = str(parsed.get("answer_text") or "").strip()
    if not answer_text:
        raise KnowledgeQueryValidationError("A tudásbázis LLM válasz nem tartalmaz answer_text mezőt")
    insufficient_source_raw = parsed.get("insufficient_source", False)
    insufficient_source = _coerce_knowledge_bool(insufficient_source_raw)
    if insufficient_source is None:
        raise KnowledgeQueryValidationError("A tudásbázis LLM válasz insufficient_source mezője nem értelmezhető boolean értékként")
    return KnowledgeAnswerPayload(
        answer_text=answer_text,
        source_summary=_normalize_source_summary(str(parsed.get("source_summary") or "").strip()),
        insufficient_source=insufficient_source,
        answer_mode=answer_mode,
    )


def _coerce_knowledge_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes", "igen"}:
            return True
        if normalized in {"false", "0", "no", "nem", ""}:
            return False
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    return None


def parse_knowledge_llm_json_object(raw_content: str) -> dict:
    try:
        return parse_llm_json_object(raw_content)
    except AnalysisModuleError as exc:
        recovered = _recover_knowledge_json_fields(raw_content)
        if recovered is None:
            raise KnowledgeQueryValidationError(str(exc)) from exc
        return recovered


def _generate_knowledge_answer(
    payload: KnowledgeQueryRequest,
    retrieved_chunks: list[KnowledgeRetrievedChunk],
) -> KnowledgeAnswerPayload:
    settings = get_settings()
    try:
        completion = LMStudioNativeProvider(settings).chat_completion(
            settings.llm_chat_model,
            [
                LLMChatMessage(role="system", content=KNOWLEDGE_QUERY_SYSTEM_PROMPT),
                LLMChatMessage(
                    role="user",
                    content=build_knowledge_query_user_prompt(payload.question, payload.answer_mode, retrieved_chunks),
                ),
            ],
            temperature=0.1,
            max_tokens=KNOWLEDGE_QUERY_MAX_OUTPUT_TOKENS,
        )
    except LLMProviderError as exc:
        raise KnowledgeQueryValidationError(str(exc)) from exc
    parsed = parse_knowledge_llm_json_object(completion.content)
    return parse_knowledge_answer_payload(parsed, payload.answer_mode)


def _knowledge_documents(db: Session, document_ids: list[UUID]) -> list[KnowledgeDocumentModel]:
    stmt = (
        select(KnowledgeDocumentModel)
        .where(
            KnowledgeDocumentModel.document_kind == "markdown_note",
            KnowledgeDocumentModel.processing_status != "archived",
        )
        .order_by(
            KnowledgeDocumentModel.relative_path.asc().nulls_last(),
            KnowledgeDocumentModel.original_filename.asc(),
            KnowledgeDocumentModel.imported_at.asc(),
        )
    )
    if document_ids:
        stmt = stmt.where(KnowledgeDocumentModel.id.in_(list(dict.fromkeys(document_ids))))
    return list(db.execute(stmt).scalars())


def _build_knowledge_source_blocks(retrieved_chunks: list[KnowledgeRetrievedChunk]) -> str:
    blocks: list[str] = []
    for index, retrieved in enumerate(retrieved_chunks, start=1):
        blocks.append(
            "\n".join(
                [
                    f"[source_{index}]",
                    f"document: {retrieved.document.original_filename}",
                    f"relative_path: {retrieved.document.relative_path or ''}",
                    f"heading_path: {retrieved.chunk.heading_path}",
                    f"chunk: {retrieved.chunk.chunk_index}",
                    "text:",
                    retrieved.chunk.text,
                ]
            )
        )
    return "\n\n".join(blocks)


def _build_used_sources(retrieved_chunks: list[KnowledgeRetrievedChunk]) -> list[KnowledgeUsedSource]:
    return [
        KnowledgeUsedSource(
            knowledge_document_id=retrieved.document.id,
            original_filename=retrieved.document.original_filename,
            relative_path=retrieved.document.relative_path,
            chunk_id=retrieved.chunk.chunk_id,
            chunk_index=retrieved.chunk.chunk_index,
            heading_path=retrieved.chunk.heading_path,
            quote_preview=_bounded_preview(retrieved.chunk.text),
            contains_code_block=retrieved.chunk.contains_code_block,
            code_languages=retrieved.chunk.code_languages,
            retrieval_score=retrieved.retrieval_score,
            retrieval_match_type=retrieved.match_type,
        )
        for retrieved in retrieved_chunks
    ]


def _placeholder_answer(payload: KnowledgeQueryRequest) -> KnowledgeAnswerPayload:
    return KnowledgeAnswerPayload(
        answer_text="A kijelölt tudásbázis-források alapján erre nem található elegendő válasz.",
        source_summary="A retrieval nem talált a kérdéshez használható tudásbázis-szövegrészt.",
        insufficient_source=True,
        answer_mode=payload.answer_mode,
    )


def _normalize_source_summary(value: str) -> str:
    normalized = " ".join(value.split())
    if len(normalized) > KNOWLEDGE_SOURCE_SUMMARY_MAX_CHARS:
        return ""
    return normalized


def _recover_knowledge_json_fields(raw_content: str) -> dict | None:
    cleaned = raw_content.strip()
    object_start = cleaned.find("{")
    object_end = cleaned.rfind("}")
    if object_start != -1 and object_end > object_start:
        cleaned = cleaned[object_start : object_end + 1]
    answer_text = _extract_json_string_field_any(cleaned, "answer_text", next_fields=["source_summary", "insufficient_source"])
    source_summary = _extract_json_string_field_any(cleaned, "source_summary", next_fields=["insufficient_source"]) or ""
    insufficient_source = _extract_json_bool_field(cleaned, "insufficient_source")
    if answer_text is None:
        return None
    return {
        "answer_text": answer_text,
        "source_summary": source_summary,
        "insufficient_source": False if insufficient_source is None else insufficient_source,
    }


def _extract_json_string_field(raw_content: str, field_name: str, *, next_field: str) -> str | None:
    pattern = rf'"{re.escape(field_name)}"\s*:\s*"(.*)"\s*,\s*"{re.escape(next_field)}"\s*:'
    match = re.search(pattern, raw_content, flags=re.DOTALL)
    if match is None:
        return None
    return _decode_json_string_fragment(match.group(1))


def _extract_json_string_field_any(raw_content: str, field_name: str, *, next_fields: list[str]) -> str | None:
    for next_field in next_fields:
        value = _extract_json_string_field(raw_content, field_name, next_field=next_field)
        if value is not None:
            return value
    pattern = rf'"{re.escape(field_name)}"\s*:\s*"(.*)"\s*\}}'
    match = re.search(pattern, raw_content, flags=re.DOTALL)
    if match is None:
        pattern = rf'"{re.escape(field_name)}"\s*:\s*"(.*)"\s*$'
        match = re.search(pattern, raw_content, flags=re.DOTALL)
        if match is None:
            pattern = rf'"{re.escape(field_name)}"\s*:\s*"(.*)$'
            match = re.search(pattern, raw_content, flags=re.DOTALL)
            if match is None:
                return None
    return _decode_json_string_fragment(match.group(1))


def _decode_json_string_fragment(value: str) -> str:
    normalized = value.replace("\r", "\\r").replace("\n", "\\n")
    try:
        return str(json.loads(f'"{normalized}"'))
    except json.JSONDecodeError:
        return (
            value.replace("\\n", "\n")
            .replace("\\r", "\r")
            .replace('\\"', '"')
            .replace("\\/", "/")
            .replace("\\\\", "\\")
        )


def _extract_json_bool_field(raw_content: str, field_name: str) -> bool | None:
    match = re.search(rf'"{re.escape(field_name)}"\s*:\s*(true|false)', raw_content)
    if match is None:
        return None
    return match.group(1) == "true"


def _bounded_preview(text: str | None, limit: int = 500) -> str:
    if text is None:
        return ""
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."
