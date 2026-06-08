from datetime import UTC, datetime
import json
import re
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analysis import AnalysisRunInputModel, AnalysisRunModel
from app.models.audit import AuditEventModel
from app.models.rag_answer import RagAnswerModel
from app.schemas.rag import (
    RagAnswerPayload,
    RagLatestRunSummary,
    RagQueryRequest,
    RagQueryResponse,
    RagRetrievalMetadata,
    RagSaveAnswerRequest,
    RagSaveAnswerResponse,
    RagSavedAnswerDetail,
    RagSavedAnswerListItem,
    RagSourceScopeSummary,
    RagUsedSource,
)
from app.schemas.analysis_modules import AnalysisModuleRunRequest
from app.services.analysis_module_common import (
    AnalysisModuleError,
    RetrievedChunk,
    order_retrieved_chunks_for_llm,
    parse_llm_json_object,
    retrieve_source_scope_chunks,
)
from app.services.analysis_runs import add_analysis_run_input, finish_analysis_run, start_analysis_run
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.document_collections import (
    CaseNotFoundError,
    DocumentCollectionNotFoundError,
    DocumentCollectionScopeError,
    ScopeResolution,
    resolve_document_scope,
)
from app.services.storage import StoragePaths
from app.services.text_store import read_chunk_text_from_store
from app.services.users import get_or_create_dev_user
from app.services.llm import LLMChatMessage, LMStudioNativeProvider


RAG_QUERY_SYSTEM_PROMPT = """Forrashu iratkerdezo komponens vagy.
A SOURCE az egyetlen igazsagforras.
A QUERY a felhasznalo kerdese vagy utasitasa.
Csak a SOURCE alapjan valaszolhatsz.
Ne hasznalj kulso tudast, ne potolj hianyzo adatot, ne feltetelezz.
Ha a SOURCE nem ad eleg alapot a valaszhoz, mondd ki roviden.
Ne allapits meg bunosseget, felelosseget, jogi minositest vagy szemelyes hibaztatast.
Ne egeszitsd ki a tortenetet emlekezetbol vagy altalanos irodalmi/targyi ismeretbol.
Ne tegyel kesz tenykent olyan allitast, amelyet a SOURCE csak feltetelezeskent, kovetkezteteskent vagy lehetosegkent fogalmaz meg.
Ha a SOURCE nem mondja ki, hogy ki kovette el a cselekmenyt, ki volt kinek a tarsa, ki vallott be valamit, vagy ki milyen szerepben vett reszt, akkor ezt ne allitsd.
Az answer_text orizze meg a SOURCE bizonyossagi szintjet: hasznalj olyan megfogalmazast, mint "a forras szerint", "Dupin kovetkeztetese szerint", "a forras ezt valoszinusiti", ha a SOURCE sem kozli erosebben.

Feladatod, hogy valaszolj a QUERY-re kizarolag a SOURCE alapjan.
A valasz legyen magyar nyelvu.
A valaszmodot az ANSWER_MODE hatarozza meg:
- short: rovid, lenyegre toro valasz.
- detailed: fejtsd ki reszletesen a valaszt, es adj vissza minden erdemi, SOURCE altal alatamasztott informaciot, amely segit a QUERY megvalaszolasaban. A reszletesseg nem jelenthet feltetelezest vagy hianyzo lancszemek potlasat.

JSON mezok:
- answer_text: a QUERY-re adott forrashu valasz.
- source_summary: legfeljebb egy rovid mondat arrol, mely SOURCE blokkok adjak a valasz alapjat. Ne ismeteld meg az answer_text tartalmat. Ha nem ad hozza hasznos informaciot, legyen ures string.
- insufficient_source: boolean. true, ha a SOURCE nem ad eleg alapot erdemi valaszhoz, kulonben false.

Csak ervenyes JSON objektumot adj vissza.
Ne irj magyarazatot, markdown blokkot vagy JSON-on kivuli szoveget.
A JSON objektumok minden mezőneve dupla idézőjelben legyen.
A JSON stringeken belüli dupla idézőjeleket escape-eld.
Az answer_text es source_summary hosszu magyar szoveg is lehet, de akkor is egyetlen ervenyes JSON string legyen.
Sortorest csak JSON escape-kent hasznalhatsz: \\n.

Elvart JSON forma:
{"answer_text":"...","source_summary":"...","insufficient_source":false}
"""

RAG_QUERY_MAX_OUTPUT_TOKENS = 2500
RAG_SOURCE_SUMMARY_MAX_CHARS = 320

RAG_DOCUMENT_ANSWER_SYSTEM_PROMPT = RAG_QUERY_SYSTEM_PROMPT + """

Tobblepcsos RAG dokumentum-reszvalasz fazisban vagy.
Csak az adott dokumentumhoz tartozo SOURCE blokkok alapjan valaszolj.
Ne probalj teljes ugyvalaszt adni, csak azt foglald ossze, hogy ez az egy dokumentum mit tamaszt ala a QUERY kapcsan.
"""

RAG_SYNTHESIS_SYSTEM_PROMPT = RAG_QUERY_SYSTEM_PROMPT + """

Tobblepcsos RAG vegso szintezis fazisban vagy.
A SOURCE most dokumentumonkenti reszvalaszokat tartalmaz, nem eredeti iratszoveget.
Csak ezekbol a reszvalaszokbol dolgozhatsz.
Ha egy reszvalasz szerint nincs eleg forras, azt kezeld ovatosan, es ne pold ki hianyzo adattal.
"""


class RagError(Exception):
    pass


class RagNotFoundError(RagError):
    pass


class RagValidationError(RagError):
    pass


class RagConflictError(RagError):
    pass


def run_rag_query(db: Session, case_id: UUID, payload: RagQueryRequest) -> RagQueryResponse:
    question = payload.question.strip()
    if not question:
        raise RagValidationError("A kérdés nem lehet üres")

    try:
        resolution = _resolve_rag_source_scope(db, case_id, payload)
    except CaseNotFoundError as exc:
        raise RagNotFoundError(str(exc)) from exc
    except DocumentCollectionNotFoundError as exc:
        raise RagNotFoundError(str(exc)) from exc
    except DocumentCollectionScopeError as exc:
        raise RagValidationError(str(exc)) from exc

    retrieved_chunks = _select_rag_source_chunks(db, case_id, payload, resolution)
    settings = get_settings()
    ordered_chunks = order_retrieved_chunks_for_llm(retrieved_chunks)
    source_scope = _source_scope_summary(case_id, payload, resolution, resolved_chunk_count=len(retrieved_chunks))
    used_sources = _build_used_sources(db, ordered_chunks)
    document_answer_count = len(_group_retrieved_chunks_by_document(ordered_chunks))
    retrieval_metadata = RagRetrievalMetadata(
        retrieval_strategy=payload.retrieval_strategy,
        max_chunks=payload.max_chunks,
        selected_chunk_count=len(retrieved_chunks),
        document_answer_count=document_answer_count,
        embedding_model=settings.llm_embedding_model if payload.retrieval_strategy in {"semantic", "hybrid"} else None,
    )
    run = start_analysis_run(
        db,
        case_id,
        "rag_query",
        provider_type="lm_studio",
        model_name=settings.llm_chat_model,
        input_parameters={
            "question": question,
            "source_mode": payload.source_mode,
            "document_id": str(payload.document_id) if payload.document_id is not None else None,
            "document_ids": [str(document_id) for document_id in payload.document_ids],
            "collection_id": str(payload.collection_id) if payload.collection_id is not None else None,
            "answer_mode": payload.answer_mode,
            "retrieval_strategy": payload.retrieval_strategy,
            "max_chunks": payload.max_chunks,
            "resolved_document_ids": [str(document_id) for document_id in resolution.resolved_document_ids],
        },
        output_schema_name="rag_answer",
        output_schema_version="v1",
        retrieval_strategy=payload.retrieval_strategy,
    )
    add_analysis_run_input(db, run.id, "query_text", 0, payload_json={"query": question})
    for sequence_no, retrieved in enumerate(ordered_chunks, start=1):
        add_analysis_run_input(
            db,
            run.id,
            "chunk",
            sequence_no,
            document_id=retrieved.chunk.document_id,
            chunk_id=retrieved.chunk.id,
            payload_json={
                "source_label": retrieved.label,
                "retrieval_score": retrieved.retrieval_score,
                "retrieval_match_type": retrieved.match_type,
            },
        )

    try:
        answer = _generate_rag_answer(db, payload, ordered_chunks)
    except Exception as exc:
        finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=str(exc))
        if isinstance(exc, RagValidationError):
            raise
        raise RagValidationError(str(exc)) from exc

    response = RagQueryResponse(
        run_id=run.id,
        answer=answer,
        source_scope=source_scope,
        used_sources=used_sources,
        retrieval_metadata=retrieval_metadata,
        can_save=True,
    )
    finish_analysis_run(
        db,
        run,
        status="succeeded",
        validation_status="warning",
        output_summary=_query_response_summary(response),
    )
    return response


def _generate_rag_answer(db: Session, payload: RagQueryRequest, retrieved_chunks: list[RetrievedChunk]) -> RagAnswerPayload:
    if not retrieved_chunks:
        return _placeholder_answer(payload, retrieved_chunks)
    document_groups = _group_retrieved_chunks_by_document(retrieved_chunks)
    if len(document_groups) <= 1:
        ordered_chunks = document_groups[0] if document_groups else order_retrieved_chunks_for_llm(retrieved_chunks)
        return _generate_single_rag_answer(
            db,
            payload,
            ordered_chunks,
            system_prompt=RAG_QUERY_SYSTEM_PROMPT,
        )

    settings = get_settings()
    partial_answers: list[tuple[str, RagAnswerPayload]] = []
    for document_chunks in document_groups:
        partial_answers.append(
            (
                document_chunks[0].document_name,
                _generate_single_rag_answer(
                    db,
                    payload,
                    document_chunks,
                    system_prompt=RAG_DOCUMENT_ANSWER_SYSTEM_PROMPT,
                ),
            )
        )
    return _generate_rag_synthesis_answer(settings, payload, partial_answers)


def _generate_single_rag_answer(
    db: Session,
    payload: RagQueryRequest,
    retrieved_chunks: list[RetrievedChunk],
    *,
    system_prompt: str,
) -> RagAnswerPayload:
    settings = get_settings()
    completion = LMStudioNativeProvider(settings).chat_completion(
        settings.llm_chat_model,
        [
            LLMChatMessage(role="system", content=system_prompt),
            LLMChatMessage(role="user", content=build_rag_query_user_prompt(db, payload.question, payload.answer_mode, retrieved_chunks)),
        ],
        temperature=0.1,
        max_tokens=RAG_QUERY_MAX_OUTPUT_TOKENS,
    )
    parsed = parse_rag_llm_json_object(completion.content)
    return parse_rag_answer_payload(parsed, payload.answer_mode)


def _generate_rag_synthesis_answer(
    settings,
    payload: RagQueryRequest,
    partial_answers: list[tuple[str, RagAnswerPayload]],
) -> RagAnswerPayload:
    completion = LMStudioNativeProvider(settings).chat_completion(
        settings.llm_chat_model,
        [
            LLMChatMessage(role="system", content=RAG_SYNTHESIS_SYSTEM_PROMPT),
            LLMChatMessage(role="user", content=build_rag_synthesis_user_prompt(payload.question, payload.answer_mode, partial_answers)),
        ],
        temperature=0.1,
        max_tokens=RAG_QUERY_MAX_OUTPUT_TOKENS,
    )
    parsed = parse_rag_llm_json_object(completion.content)
    return parse_rag_answer_payload(parsed, payload.answer_mode)


def _select_rag_source_chunks(
    db: Session,
    case_id: UUID,
    payload: RagQueryRequest,
    resolution: ScopeResolution,
) -> list[RetrievedChunk]:
    retrieval_payload = AnalysisModuleRunRequest(
        query=payload.question,
        source_mode="case",
        document_ids=resolution.resolved_document_ids,
        max_chunks=payload.max_chunks,
        retrieval_strategy=payload.retrieval_strategy,
    )
    return retrieve_source_scope_chunks(
        db,
        case_id,
        retrieval_payload,
        document_ids=resolution.resolved_document_ids,
    )


def _group_retrieved_chunks_by_document(retrieved_chunks: list[RetrievedChunk]) -> list[list[RetrievedChunk]]:
    groups: list[list[RetrievedChunk]] = []
    current_group: list[RetrievedChunk] = []
    current_document_id: UUID | None = None
    for retrieved in order_retrieved_chunks_for_llm(retrieved_chunks):
        document_id = retrieved.chunk.document_id
        if current_group and document_id != current_document_id:
            groups.append(current_group)
            current_group = []
        current_group.append(retrieved)
        current_document_id = document_id
    if current_group:
        groups.append(current_group)
    return groups


def _placeholder_answer(payload: RagQueryRequest, retrieved_chunks: list[RetrievedChunk]) -> RagAnswerPayload:
    if not retrieved_chunks:
        return RagAnswerPayload(
            answer_text="A kijelölt források alapján erre nem található elegendő válasz.",
            source_summary="A retrieval nem talált a kérdéshez használható szövegrészt a kijelölt forráskörben.",
            insufficient_source=True,
            answer_mode=payload.answer_mode,
        )
    return RagAnswerPayload(
        answer_text="A kérdéshez találtam forrásszövegeket, de a természetes nyelvű RAG válasz generálása még nincs bekötve ebben az implementációs szeletben.",
        source_summary=f"A retrieval {len(retrieved_chunks)} szövegrészt választott ki a kijelölt forráskörből.",
        insufficient_source=True,
        answer_mode=payload.answer_mode,
    )


def build_rag_query_user_prompt(
    db: Session,
    question: str,
    answer_mode: str,
    retrieved_chunks: list[RetrievedChunk],
) -> str:
    return (
        f"QUERY:\n{question.strip()}\n\n"
        f"ANSWER_MODE:\n{answer_mode}\n\n"
        f"SOURCE:\n{_build_rag_source_blocks(db, retrieved_chunks)}"
    )


def build_rag_synthesis_user_prompt(
    question: str,
    answer_mode: str,
    partial_answers: list[tuple[str, RagAnswerPayload]],
) -> str:
    answer_blocks: list[str] = []
    for index, (document_name, answer) in enumerate(partial_answers, start=1):
        answer_blocks.append(
            "\n".join(
                [
                    f"[document_answer_{index}]",
                    f"document: {document_name}",
                    f"insufficient_source: {str(answer.insufficient_source).lower()}",
                    "answer_text:",
                    answer.answer_text,
                    "source_summary:",
                    answer.source_summary,
                ]
            )
        )
    return (
        f"QUERY:\n{question.strip()}\n\n"
        f"ANSWER_MODE:\n{answer_mode}\n\n"
        f"SOURCE:\n{chr(10).join(answer_blocks)}"
    )


def parse_rag_answer_payload(parsed: dict, answer_mode: str) -> RagAnswerPayload:
    answer_text = str(parsed.get("answer_text") or "").strip()
    if not answer_text:
        raise RagValidationError("A RAG LLM válasz nem tartalmaz answer_text mezőt")
    source_summary = _normalize_rag_source_summary(str(parsed.get("source_summary") or "").strip())
    insufficient_source_raw = parsed.get("insufficient_source")
    if not isinstance(insufficient_source_raw, bool):
        raise RagValidationError("A RAG LLM válasz insufficient_source mezője nem boolean")
    return RagAnswerPayload(
        answer_text=answer_text,
        source_summary=source_summary,
        insufficient_source=insufficient_source_raw,
        answer_mode=answer_mode,
    )


def _normalize_rag_source_summary(value: str) -> str:
    normalized = " ".join(value.split())
    if len(normalized) > RAG_SOURCE_SUMMARY_MAX_CHARS:
        return ""
    return normalized


def parse_rag_llm_json_object(raw_content: str) -> dict:
    try:
        return parse_llm_json_object(raw_content)
    except AnalysisModuleError as exc:
        recovered = _recover_rag_json_fields(raw_content)
        if recovered is None:
            raise exc
        return recovered


def _recover_rag_json_fields(raw_content: str) -> dict | None:
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
            value
            .replace("\\n", "\n")
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


def _build_rag_source_blocks(db: Session, retrieved_chunks: list[RetrievedChunk]) -> str:
    blocks: list[str] = []
    for index, retrieved in enumerate(retrieved_chunks, start=1):
        chunk = retrieved.chunk
        blocks.append(
            "\n".join(
                [
                    f"[source_{index}]",
                    f"document: {retrieved.document_name}",
                    f"page: {chunk.page_start}",
                    f"chunk: {chunk.chunk_index}",
                    "text:",
                    read_chunk_text_from_store(db, chunk),
                ]
            )
        )
    return "\n\n".join(blocks)


def _build_used_sources(db: Session, retrieved_chunks: list[RetrievedChunk]) -> list[RagUsedSource]:
    sources: list[RagUsedSource] = []
    for retrieved in retrieved_chunks:
        chunk = retrieved.chunk
        sources.append(
            RagUsedSource(
                document_id=chunk.document_id,
                document_filename=retrieved.document_name,
                page_number=chunk.page_start,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                quote_preview=_bounded_preview(read_chunk_text_from_store(db, chunk)),
                retrieval_score=retrieved.retrieval_score,
                retrieval_match_type=retrieved.match_type,
            )
        )
    return sources


def save_rag_answer(
    db: Session,
    case_id: UUID,
    run_id: UUID,
    payload: RagSaveAnswerRequest,
) -> RagSaveAnswerResponse:
    run = _require_rag_run(db, case_id, run_id)
    existing = _answer_for_run(db, run.id)
    if existing is not None:
        return RagSaveAnswerResponse(answer_id=existing.id, run_id=run.id, saved=False)

    summary = _require_rag_run_summary(db, run)
    answer_payload = summary.get("answer") if isinstance(summary.get("answer"), dict) else {}
    answer_text = str(answer_payload.get("answer_text") or "").strip()
    if not answer_text:
        raise RagValidationError("A RAG futás nem tartalmaz menthető választ")

    source_scope = summary.get("source_scope") if isinstance(summary.get("source_scope"), dict) else {}
    used_sources = summary.get("used_sources") if isinstance(summary.get("used_sources"), list) else []
    retrieval_metadata = summary.get("retrieval_metadata") if isinstance(summary.get("retrieval_metadata"), dict) else {}
    retrieval_metadata = {
        **retrieval_metadata,
        "source_summary": str(answer_payload.get("source_summary") or "").strip(),
    }
    question = str((run.input_parameters or {}).get("question") or "").strip()
    answer_mode = str(answer_payload.get("answer_mode") or (run.input_parameters or {}).get("answer_mode") or "detailed")
    user = get_or_create_dev_user(db)
    answer = RagAnswerModel(
        case_id=case_id,
        analysis_run_id=run.id,
        title=payload.title.strip() if payload.title and payload.title.strip() else _default_title(question),
        question=question,
        answer_text=answer_text,
        answer_mode=answer_mode,
        source_scope_json=source_scope,
        used_sources_json=used_sources,
        retrieval_metadata_json=retrieval_metadata,
        model_name=run.model_name,
        note=payload.note.strip() if payload.note and payload.note.strip() else None,
        created_at=datetime.now(UTC),
        created_by_user_id=user.id,
    )
    db.add(answer)
    db.flush()
    _write_audit(
        db,
        event_type="rag_answer_saved",
        case_id=case_id,
        user_id=user.id,
        analysis_run_id=run.id,
        answer_id=answer.id,
        input_summary={"run_id": str(run.id)},
        output_summary={"answer_id": str(answer.id), "used_source_count": len(used_sources)},
    )
    db.commit()
    db.refresh(answer)
    return RagSaveAnswerResponse(answer_id=answer.id, run_id=run.id, saved=True)


def list_rag_answers(db: Session, case_id: UUID) -> list[RagSavedAnswerListItem]:
    answers = list(
        db.execute(
            select(RagAnswerModel)
            .where(RagAnswerModel.case_id == case_id)
            .order_by(RagAnswerModel.created_at.desc(), RagAnswerModel.id)
        )
        .scalars()
        .all()
    )
    return [_list_item(answer) for answer in answers]


def get_rag_answer(db: Session, case_id: UUID, answer_id: UUID) -> RagSavedAnswerDetail:
    answer = db.get(RagAnswerModel, answer_id)
    if answer is None or answer.case_id != case_id:
        raise RagNotFoundError("RAG válasz nem található")
    return _detail(answer)


def delete_rag_answer(db: Session, case_id: UUID, answer_id: UUID) -> None:
    answer = db.get(RagAnswerModel, answer_id)
    if answer is None or answer.case_id != case_id:
        raise RagNotFoundError("RAG válasz nem található")
    user = get_or_create_dev_user(db)
    db.delete(answer)
    _write_audit(
        db,
        event_type="rag_answer_deleted",
        case_id=case_id,
        user_id=user.id,
        analysis_run_id=answer.analysis_run_id,
        answer_id=answer.id,
        input_summary={"answer_id": str(answer.id)},
        output_summary={"deleted": True},
    )
    db.commit()


def get_latest_rag_run_summary(db: Session, case_id: UUID) -> RagLatestRunSummary | None:
    run = (
        db.execute(
            select(AnalysisRunModel)
            .where(AnalysisRunModel.case_id == case_id, AnalysisRunModel.run_type == "rag_query")
            .order_by(AnalysisRunModel.started_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if run is None:
        return None

    input_parameters = run.input_parameters if isinstance(run.input_parameters, dict) else {}
    output_summary: dict = {}
    if run.status == "succeeded":
        try:
            output_summary = _require_rag_run_summary(db, run)
        except RagValidationError:
            output_summary = {}

    answer = output_summary.get("answer") if isinstance(output_summary.get("answer"), dict) else {}
    source_scope = output_summary.get("source_scope") if isinstance(output_summary.get("source_scope"), dict) else {}
    retrieval_metadata = (
        output_summary.get("retrieval_metadata")
        if isinstance(output_summary.get("retrieval_metadata"), dict)
        else {}
    )
    used_sources = output_summary.get("used_sources") if isinstance(output_summary.get("used_sources"), list) else []
    saved_answer = _answer_for_run(db, run.id)
    input_chunk_count = (
        db.execute(
            select(func.count())
            .select_from(AnalysisRunInputModel)
            .where(AnalysisRunInputModel.analysis_run_id == run.id, AnalysisRunInputModel.input_type == "chunk")
        ).scalar_one()
        or 0
    )

    source_mode = source_scope.get("source_mode") or input_parameters.get("source_mode")
    answer_mode = answer.get("answer_mode") or input_parameters.get("answer_mode")
    retrieval_strategy = retrieval_metadata.get("retrieval_strategy") or input_parameters.get("retrieval_strategy")

    return RagLatestRunSummary(
        analysis_run_id=run.id,
        status=run.status,
        validation_status=run.validation_status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        question=str(input_parameters.get("question") or "") or None,
        source_mode=source_mode if source_mode in {"case", "document", "collection"} else None,
        document_id=source_scope.get("document_id") or input_parameters.get("document_id"),
        collection_id=source_scope.get("collection_id") or input_parameters.get("collection_id"),
        answer_mode=answer_mode if answer_mode in {"short", "detailed"} else None,
        retrieval_strategy=retrieval_strategy if retrieval_strategy in {"keyword", "semantic", "hybrid"} else None,
        max_chunks=_optional_int(retrieval_metadata.get("max_chunks") or input_parameters.get("max_chunks")),
        selected_chunk_count=_optional_int(retrieval_metadata.get("selected_chunk_count")) or int(input_chunk_count),
        document_answer_count=_optional_int(retrieval_metadata.get("document_answer_count")) or 0,
        used_source_count=len(used_sources),
        insufficient_source=answer.get("insufficient_source") if isinstance(answer.get("insufficient_source"), bool) else None,
        saved_answer_id=saved_answer.id if saved_answer is not None else None,
        error_message=run.error_message,
    )


def _resolve_rag_source_scope(db: Session, case_id: UUID, payload: RagQueryRequest) -> ScopeResolution:
    if payload.source_mode == "case":
        return resolve_document_scope(
            db,
            case_id,
            "documents" if payload.document_ids else "case",
            document_ids=payload.document_ids or None,
        )
    if payload.source_mode == "document":
        return resolve_document_scope(db, case_id, "documents", document_ids=[payload.document_id])
    if payload.source_mode == "collection":
        return resolve_document_scope(db, case_id, "collections", collection_ids=[payload.collection_id])
    raise RagValidationError("Ismeretlen forráskör")


def _source_scope_summary(
    case_id: UUID,
    payload: RagQueryRequest,
    resolution: ScopeResolution,
    *,
    resolved_chunk_count: int,
) -> RagSourceScopeSummary:
    return RagSourceScopeSummary(
        source_mode=payload.source_mode,
        case_id=case_id,
        document_id=payload.document_id,
        collection_id=payload.collection_id,
        resolved_document_count=resolution.resolved_document_count,
        resolved_chunk_count=resolved_chunk_count,
        inactive_document_count=resolution.inactive_document_count,
        duplicate_membership_count=resolution.duplicate_membership_count,
        warnings=resolution.warnings,
    )


def _query_response_summary(response: RagQueryResponse) -> dict:
    return {
        "answer": response.answer.model_dump(mode="json"),
        "source_scope": response.source_scope.model_dump(mode="json"),
        "used_sources": [source.model_dump(mode="json") for source in response.used_sources],
        "retrieval_metadata": response.retrieval_metadata.model_dump(mode="json"),
        "can_save": response.can_save,
    }


def _require_rag_run(db: Session, case_id: UUID, run_id: UUID) -> AnalysisRunModel:
    run = db.get(AnalysisRunModel, run_id)
    if run is None or run.case_id != case_id:
        raise RagNotFoundError("RAG futás nem található")
    if run.run_type != "rag_query":
        raise RagValidationError("Csak RAG kérdező futás menthető RAG válaszként")
    if run.status != "succeeded":
        raise RagValidationError("Csak sikeres RAG futás menthető")
    return run


def _answer_for_run(db: Session, run_id: UUID) -> RagAnswerModel | None:
    return db.execute(select(RagAnswerModel).where(RagAnswerModel.analysis_run_id == run_id)).scalar_one_or_none()


def _require_rag_run_summary(db: Session, run: AnalysisRunModel) -> dict:
    audit = (
        db.execute(
            select(AuditEventModel)
            .where(
                AuditEventModel.analysis_run_id == run.id,
                AuditEventModel.event_type == "analysis_run_succeeded",
                AuditEventModel.success.is_(True),
            )
            .order_by(AuditEventModel.event_timestamp.desc(), AuditEventModel.created_at.desc())
        )
        .scalars()
        .first()
    )
    if audit is None or not isinstance(audit.output_summary, dict):
        raise RagValidationError("A RAG futás nem tartalmaz menthető válaszösszegzést")
    return audit.output_summary


def _list_item(answer: RagAnswerModel) -> RagSavedAnswerListItem:
    source_scope = answer.source_scope_json or {}
    return RagSavedAnswerListItem(
        id=answer.id,
        title=answer.title,
        question=answer.question,
        answer_mode=answer.answer_mode,
        source_mode=str(source_scope.get("source_mode") or ""),
        source_label=_source_label(source_scope),
        created_at=answer.created_at,
        used_source_count=len(answer.used_sources_json or []),
    )


def _detail(answer: RagAnswerModel) -> RagSavedAnswerDetail:
    retrieval_metadata = answer.retrieval_metadata_json or {}
    return RagSavedAnswerDetail(
        id=answer.id,
        case_id=answer.case_id,
        analysis_run_id=answer.analysis_run_id,
        title=answer.title,
        question=answer.question,
        answer_text=answer.answer_text,
        source_summary=str(retrieval_metadata.get("source_summary") or ""),
        answer_mode=answer.answer_mode,
        source_scope=answer.source_scope_json or {},
        used_sources=answer.used_sources_json or [],
        retrieval_metadata=retrieval_metadata,
        model_name=answer.model_name,
        note=answer.note,
        created_at=answer.created_at,
    )


def _source_label(source_scope: dict) -> str | None:
    mode = source_scope.get("source_mode")
    if mode == "case":
        return "Teljes ügy"
    if mode == "document":
        return "Kijelölt irat"
    if mode == "collection":
        return "Iratgyűjtemény"
    return None


def _optional_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _default_title(question: str) -> str:
    normalized = " ".join(question.split())
    if not normalized:
        return "Mentett iratkérdező válasz"
    if len(normalized) <= 100:
        return normalized
    return f"{normalized[:100].rstrip()}..."


def _bounded_preview(text: str | None, limit: int = 360) -> str:
    if text is None:
        return ""
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."


def _write_audit(
    db: Session,
    *,
    event_type: str,
    case_id: UUID,
    user_id: UUID,
    analysis_run_id: UUID,
    answer_id: UUID,
    input_summary: dict,
    output_summary: dict,
) -> None:
    event = AuditEvent(
        event_type=event_type,
        success=True,
        case_id=str(case_id),
        user_id=str(user_id),
        analysis_run_id=str(analysis_run_id),
        related_object_type="rag_answer",
        related_object_id=str(answer_id),
        input_summary=input_summary,
        output_summary=output_summary,
    )
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(event)
    DatabaseAuditWriter(db).write(event)
