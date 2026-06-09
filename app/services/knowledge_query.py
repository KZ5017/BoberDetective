from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.knowledge import KnowledgeDocumentModel
from app.schemas.knowledge import (
    KnowledgeAnswerPayload,
    KnowledgeIndexRequest,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    KnowledgeRetrievalMetadata,
    KnowledgeUsedSource,
)
from app.services.analysis_module_common import AnalysisModuleError, parse_llm_json_object
from app.services.knowledge_import import KnowledgeStoredChunk, read_knowledge_chunks
from app.services.knowledge_indexing import (
    KnowledgeIndexError,
    QdrantKnowledgeIndex,
    get_knowledge_index_status,
    knowledge_collection_name,
)
from app.services.llm import LLMChatMessage, LLMProviderError, LMStudioNativeProvider, get_llm_provider


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
- answer_text: a QUERY-re adott forrashu valasz.
- source_summary: legfeljebb egy rovid mondat arrol, mely SOURCE blokkok adjak a valasz alapjat. Ne ismeteld meg az answer_text tartalmat. Ha nem ad hozza hasznos informaciot, legyen ures string.
- insufficient_source: boolean. true, ha a SOURCE nem ad eleg alapot erdemi valaszhoz, kulonben false.

Csak ervenyes JSON objektumot adj vissza.
Ne irj magyarazatot, markdown blokkot vagy JSON-on kivuli szoveget.
A JSON objektumok minden mezőneve dupla idézőjelben legyen.
A JSON stringeken belüli dupla idézőjeleket escape-eld.
Sortorest csak JSON escape-kent hasznalhatsz: \\n.

Elvart JSON forma:
{"answer_text":"...","source_summary":"...","insufficient_source":false}
"""

KNOWLEDGE_QUERY_MAX_OUTPUT_TOKENS = 2500
KNOWLEDGE_SOURCE_SUMMARY_MAX_CHARS = 320
KNOWLEDGE_STOPWORDS = {
    "a",
    "az",
    "egy",
    "és",
    "es",
    "vagy",
    "hogy",
    "mit",
    "mi",
    "milyen",
    "hogyan",
    "mikor",
    "hol",
    "van",
    "vannak",
    "kell",
    "lehet",
    "tudok",
    "tudunk",
    "keress",
    "keresd",
    "adj",
    "valasz",
    "válasz",
}


class KnowledgeQueryError(Exception):
    pass


class KnowledgeQueryValidationError(KnowledgeQueryError):
    pass


@dataclass(frozen=True)
class KnowledgeRetrievedChunk:
    label: str
    document: KnowledgeDocumentModel
    chunk: KnowledgeStoredChunk
    retrieval_score: float
    match_type: str


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
        else _generate_knowledge_answer(payload, _order_retrieved_chunks_for_llm(retrieved_chunks))
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
        return _keyword_knowledge_search(documents, payload.question, payload.max_chunks)
    if payload.retrieval_strategy == "semantic":
        return _semantic_knowledge_search(db, documents, payload.question, payload.max_chunks)
    keyword_hits = _keyword_knowledge_search(documents, payload.question, payload.max_chunks)
    semantic_hits = _semantic_knowledge_search(db, documents, payload.question, payload.max_chunks)
    return _merge_hybrid_hits(keyword_hits, semantic_hits, payload.max_chunks)


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
    insufficient_source_raw = parsed.get("insufficient_source")
    if not isinstance(insufficient_source_raw, bool):
        raise KnowledgeQueryValidationError("A tudásbázis LLM válasz insufficient_source mezője nem boolean")
    return KnowledgeAnswerPayload(
        answer_text=answer_text,
        source_summary=_normalize_source_summary(str(parsed.get("source_summary") or "").strip()),
        insufficient_source=insufficient_source_raw,
        answer_mode=answer_mode,
    )


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


def _keyword_knowledge_search(
    documents: list[KnowledgeDocumentModel],
    query: str,
    limit: int,
) -> list[KnowledgeRetrievedChunk]:
    terms = _query_terms(query)
    exact = " ".join(query.casefold().split())
    candidates: list[KnowledgeRetrievedChunk] = []
    for document in documents:
        for chunk in read_knowledge_chunks(document):
            text = " ".join(chunk.text.casefold().split())
            score = 0.0
            if exact and exact in text:
                score += 2.5
            score += sum(1.0 for term in terms if term in text)
            if score <= 0:
                continue
            candidates.append(
                KnowledgeRetrievedChunk(
                    label="",
                    document=document,
                    chunk=chunk,
                    retrieval_score=round(score, 6),
                    match_type="keyword",
                )
            )
    ranked = sorted(
        candidates,
        key=lambda item: (
            -item.retrieval_score,
            item.document.relative_path or item.document.original_filename,
            item.chunk.chunk_index,
        ),
    )[:limit]
    return _relabel(ranked)


def _semantic_knowledge_search(
    db: Session,
    documents: list[KnowledgeDocumentModel],
    query: str,
    limit: int,
) -> list[KnowledgeRetrievedChunk]:
    status = get_knowledge_index_status(db, KnowledgeIndexRequest(document_ids=[item.id for item in documents]))
    if status.chunk_count == 0:
        return []
    if not status.is_ready:
        raise KnowledgeQueryValidationError(
            "A szemantikus vagy hybrid tudásbázis kereséshez előbb indexelni kell a kijelölt tudásbázis dokumentumokat "
            f"az aktuális embedding modellel ({status.embedding_model}). "
            f"Indexelve: {status.indexed_chunk_count}/{status.chunk_count}."
        )
    settings = get_settings()
    try:
        embedding_result = get_llm_provider(settings).embeddings(settings.llm_embedding_model, [query])
        semantic_hits = QdrantKnowledgeIndex(settings).search(
            query_embedding=embedding_result.embeddings[0],
            limit=limit,
            document_ids=[item.id for item in documents],
        )
    except (LLMProviderError, KnowledgeIndexError) as exc:
        raise KnowledgeQueryValidationError(str(exc)) from exc
    documents_by_id = {document.id: document for document in documents}
    chunks_by_document = {document.id: {chunk.chunk_id: chunk for chunk in read_knowledge_chunks(document)} for document in documents}
    retrieved: list[KnowledgeRetrievedChunk] = []
    for hit in semantic_hits:
        document = documents_by_id.get(hit.knowledge_document_id)
        chunk = chunks_by_document.get(hit.knowledge_document_id, {}).get(hit.chunk_id)
        if document is None or chunk is None:
            continue
        retrieved.append(KnowledgeRetrievedChunk("", document, chunk, hit.score, hit.match_type))
    return _relabel(retrieved)


def _merge_hybrid_hits(
    keyword_hits: list[KnowledgeRetrievedChunk],
    semantic_hits: list[KnowledgeRetrievedChunk],
    limit: int,
) -> list[KnowledgeRetrievedChunk]:
    candidates: dict[tuple[UUID, str], KnowledgeRetrievedChunk] = {}
    max_keyword_score = max((hit.retrieval_score for hit in keyword_hits), default=0.0)
    for hit in keyword_hits:
        score = (hit.retrieval_score / max_keyword_score) * 0.35 if max_keyword_score > 0 else 0.0
        candidates[(hit.document.id, hit.chunk.chunk_id)] = KnowledgeRetrievedChunk(
            "",
            hit.document,
            hit.chunk,
            round(score, 6),
            "keyword",
        )
    for hit in semantic_hits:
        key = (hit.document.id, hit.chunk.chunk_id)
        semantic_score = min(1.0, max(0.0, hit.retrieval_score)) * 0.55
        existing = candidates.get(key)
        if existing is None:
            candidates[key] = KnowledgeRetrievedChunk("", hit.document, hit.chunk, round(semantic_score, 6), "semantic")
        else:
            candidates[key] = KnowledgeRetrievedChunk(
                "",
                hit.document,
                hit.chunk,
                round(existing.retrieval_score + semantic_score + 0.2, 6),
                "hybrid",
            )
    ranked = sorted(
        candidates.values(),
        key=lambda item: (
            -item.retrieval_score,
            item.document.relative_path or item.document.original_filename,
            item.chunk.chunk_index,
        ),
    )[:limit]
    return _relabel(ranked)


def _order_retrieved_chunks_for_llm(retrieved_chunks: list[KnowledgeRetrievedChunk]) -> list[KnowledgeRetrievedChunk]:
    ordered = sorted(
        retrieved_chunks,
        key=lambda item: (
            item.document.relative_path or item.document.original_filename,
            item.document.original_filename,
            item.chunk.chunk_index,
        ),
    )
    return _relabel(ordered)


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


def _query_terms(query: str) -> list[str]:
    terms: list[str] = []
    for term in re.findall(r"[\wáéíóöőúüűÁÉÍÓÖŐÚÜŰ'-]+", query.casefold()):
        if len(term) < 2 or term in KNOWLEDGE_STOPWORDS:
            continue
        terms.append(term)
    return list(dict.fromkeys(terms))


def _relabel(retrieved_chunks: list[KnowledgeRetrievedChunk]) -> list[KnowledgeRetrievedChunk]:
    return [
        KnowledgeRetrievedChunk(
            label=f"source_{index}",
            document=retrieved.document,
            chunk=retrieved.chunk,
            retrieval_score=retrieved.retrieval_score,
            match_type=retrieved.match_type,
        )
        for index, retrieved in enumerate(retrieved_chunks, start=1)
    ]


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
    answer_text = _extract_json_string_field(cleaned, "answer_text", next_field="source_summary")
    source_summary = _extract_json_string_field(cleaned, "source_summary", next_field="insufficient_source")
    insufficient_source = _extract_json_bool_field(cleaned, "insufficient_source")
    if answer_text is None or source_summary is None or insufficient_source is None:
        return None
    return {
        "answer_text": answer_text,
        "source_summary": source_summary,
        "insufficient_source": insufficient_source,
    }


def _extract_json_string_field(raw_content: str, field_name: str, *, next_field: str) -> str | None:
    pattern = rf'"{re.escape(field_name)}"\s*:\s*"(.*)"\s*,\s*"{re.escape(next_field)}"\s*:'
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
