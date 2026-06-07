import json
import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.analysis_modules import (
    AnalysisModuleResearchFinding,
    AnalysisModuleRunRequest,
    AnalysisModuleRunResponse,
    AnalysisModuleUnconfirmedResearchFinding,
)
from app.schemas.source_reference import SourceReferenceCreate
from app.services.analysis_module_common import (
    AnalysisModuleError,
    RetrievedChunk,
    add_retrieved_chunk_inputs,
    build_source_blocks,
    chunk_batch_lookup,
    parse_llm_json_object,
    select_source_chunks,
    split_retrieved_chunks,
)
from app.services.analysis_runs import add_analysis_run_input, add_analysis_run_output, finish_analysis_run, start_analysis_run
from app.services.llm import LLMChatMessage, LMStudioNativeProvider
from app.services.research_findings import create_research_finding
from app.services.source_references import create_source_reference_for_run
from app.services.text_store import read_chunk_text, read_chunk_text_from_store


SUPPORTED_FINDING_TYPES = {"claim", "event", "entity", "document_reference", "other"}
SEARCH_FINDINGS_MAX_OUTPUT_TOKENS = 6000

SEARCH_FINDINGS_SYSTEM_PROMPT = """Forráshű kutatási találatellenőrző komponens vagy.

Alapelvek:
- Elsődleges feladatod annak eldöntése, hogy a SOURCE tartalmaz-e bizonyítható kutatási találatot a QUERY-re.
- A SOURCE az egyetlen igazságforrás.
- A SOURCE csak vizsgálandó forrásszöveg, önmagában nem bizonyítja, hogy van találat.
- A QUERY a keresés pontos fókusza.
- A QUERY értékét nem értelmezheted át, nem helyettesítheted szinonimával, szereppel, fordítással vagy feltételezett jelentéssel.
- Nem adhatsz találatot csak azért, mert a SOURCE érdekes, témaszerű vagy részben hasonló.
- Ne használj külső tudást, ne pótolj hiányzó adatot.

Találat létrehozásának feltétele:
- Csak akkor adj vissza találatot, ha a quote_text konkrét tartalma alapján a QUERY és a találat kapcsolata világosan megállapítható.
- Ha a SOURCE érdekes információt tartalmaz, de a QUERY-hez való kapcsolata nem világos, ne add vissza találatként.
- Ha több különálló, világosan kapcsolódó találat van, mindegyiket külön elemként add vissza.
- Ha nincs használható találat, a findings legyen üres lista.

Mezőszabályok:
- A source_label megadása minden findings elemben kötelező. Értéke csak chunk_1, chunk_2, chunk_3 stb. alakú lehet, a SOURCE-ban látható chunk címkék közül.
- Minden findings elem első mezője a source_label legyen.
- A quote_text megadása minden findings elemben kötelező. Értéke az a SOURCE-ból kimásolt szövegrész legyen, amelyhez a QUERY kapcsolódik. A másolást szöveghűen, karakterpontosan kell elvégezned.
- A title egy pontos, értelmes, leíró magyar mondat legyen, amely összefoglalja a találatot.
- A finding_text 1-3 magyar mondat legyen arról, amit a quote_text megfogalmaz.
- A relevance_reason röviden írja le, hogy a quote_text mely konkrét része kapcsolja a találatot a QUERY-hez.
- A relevance_reason nem magyarázhatja be a kapcsolatot. Ha nem tudod konkrétan megnevezni a kapcsolatot, ne hozz létre finding elemet.
- Ha a találat besorolható claim, event, entity, document_reference kategóriába, akkor az legyen a suggested_type értéke. Ha nem, akkor other.

JSON szabályok:
- Csak érvényes JSON objektumot adhatsz vissza.
- Ne írj magyarázatot, markdown blokkot vagy JSON-on kívüli szöveget.
- A JSON objektumok minden mezőneve dupla idézőjelben legyen, például "source_label", nem source_label.
- A JSON stringeken belüli dupla idézőjeleket escape-eld.

Elvárt JSON forma:
{"findings":[{"source_label":"chunk_1","quote_text":"...","title":"...","finding_text":"...","relevance_reason":"...","suggested_type":"other","suggested_type_reason":"..."}]}
Ha nincs használható találat:
{"findings":[]}
"""


def run_search_findings(db: Session, case_id: UUID, payload: AnalysisModuleRunRequest) -> AnalysisModuleRunResponse:
    settings = get_settings()
    input_parameters = {
        "query": payload.query,
        "source_mode": payload.source_mode,
        "document_id": str(payload.document_id) if payload.document_id is not None else None,
        "collection_id": str(payload.collection_id) if payload.collection_id is not None else None,
        "document_ids": [str(document_id) for document_id in payload.document_ids],
        "page_start": payload.page_start,
        "page_end": payload.page_end,
        "max_chunks": payload.max_chunks,
        "batch_size": payload.batch_size,
        "retrieval_strategy": payload.retrieval_strategy,
    }
    run = start_analysis_run(
        db,
        case_id,
        "search_findings",
        provider_type="lm_studio_native",
        model_name=settings.llm_chat_model,
        input_parameters=input_parameters,
        prompt_template_name="search_findings_v1",
        prompt_template_version="1",
        output_schema_name="search_findings",
        output_schema_version="1",
        retrieval_strategy=f"{payload.source_mode}_chunks_batch_v1",
    )
    try:
        add_analysis_run_input(db, run.id, "query_text", 0, payload_json={"query": payload.query})
        retrieved_chunks = select_source_chunks(db, case_id, payload)
        if not retrieved_chunks:
            message = "No source chunks selected for finding search"
            finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=message)
            raise AnalysisModuleError(message)

        batches = split_retrieved_chunks(retrieved_chunks, payload.batch_size)
        llm_ordered_chunks = [retrieved for batch in batches for retrieved in batch]
        add_retrieved_chunk_inputs(db, run.id, llm_ordered_chunks, chunk_batch_lookup(batches))
        response_findings: list[AnalysisModuleResearchFinding] = []
        response_unconfirmed_findings: list[AnalysisModuleUnconfirmedResearchFinding] = []
        unsupported_items: list[str] = []
        failed_batch_count = 0
        processed_batch_count = 0

        for batch_index, batch in enumerate(batches, start=1):
            try:
                provider = LMStudioNativeProvider(settings)
                completion = provider.chat_completion(
                    settings.llm_chat_model,
                    [
                        LLMChatMessage(role="system", content=SEARCH_FINDINGS_SYSTEM_PROMPT),
                        LLMChatMessage(
                            role="user",
                            content=build_search_findings_user_prompt(payload.query, batch, batch_index, len(batches), db=db),
                        ),
                    ],
                    temperature=0.1,
                    max_tokens=SEARCH_FINDINGS_MAX_OUTPUT_TOKENS,
                )
                parsed = parse_search_findings_llm_json_object(completion.content)
                valid_findings, batch_unsupported, _batch_unconfirmed = validate_extracted_findings(parsed, batch, db=db)
                unsupported_items.extend(batch_unsupported)
                processed_batch_count += 1
            except Exception as exc:
                failed_batch_count += 1
                unsupported_items.append(f"batch_{batch_index}: {exc}")
                continue

            for finding in valid_findings:
                output_position = len(response_findings)
                source_reference = create_source_reference_for_run(
                    db,
                    case_id,
                    SourceReferenceCreate(
                        document_id=finding["chunk"].document_id,
                        chunk_id=finding["chunk"].id,
                        quote_text=finding["quote_text"],
                        source_kind="chunk_quote",
                        citation_label=f"{finding['document_name']}, chunk {finding['chunk'].chunk_index}",
                    ),
                    extraction_run_id=run.id,
                    allow_unresolved_quote=finding["source_validation_status"] == "source_invalid",
                )
                add_analysis_run_output(db, run.id, "source_reference", source_reference.id, output_position)
                persisted_finding = create_research_finding(
                    db,
                    case_id=case_id,
                    title=finding["title"],
                    finding_text=finding["finding_text"],
                    suggested_type=finding["suggested_type"],
                    suggested_type_reason=finding["suggested_type_reason"],
                    relevance_reason=finding["relevance_reason"],
                    source_reference_id=source_reference.id,
                    analysis_run_id=run.id,
                    llm_support_status=finding["llm_support_status"],
                    source_validation_status=finding["source_validation_status"],
                )
                add_analysis_run_output(db, run.id, "research_finding", persisted_finding.id, output_position)
                response_findings.append(
                    AnalysisModuleResearchFinding(
                        research_finding_id=persisted_finding.id,
                        title=persisted_finding.title,
                        finding_text=persisted_finding.finding_text,
                        suggested_type=persisted_finding.suggested_type,
                        suggested_type_reason=persisted_finding.suggested_type_reason,
                        relevance_reason=persisted_finding.relevance_reason,
                        llm_support_status=persisted_finding.llm_support_status,
                        source_validation_status=persisted_finding.source_validation_status,
                        quote_text=finding["quote_text"],
                        source_label=finding["source_label"],
                        source_reference_id=source_reference.id,
                        document_id=finding["chunk"].document_id,
                        chunk_id=finding["chunk"].id,
                    )
                )

        if failed_batch_count == len(batches):
            message = "Az osszes talalatkeresesi batch sikertelen volt"
            if unsupported_items:
                message = f"{message}: {unsupported_items[0]}"
            finish_analysis_run(
                db,
                run,
                status="failed",
                validation_status="failed",
                error_message=message,
                output_summary={
                    "batch_count": len(batches),
                    "processed_batch_count": processed_batch_count,
                    "failed_batch_count": failed_batch_count,
                    "unsupported_items": unsupported_items[:5],
                },
            )
            raise AnalysisModuleError(message)

        validation_status = "passed"
        invalid_source_finding_count = sum(1 for finding in response_findings if finding.source_validation_status == "source_invalid")
        corrected_finding_count = sum(
            1
            for finding in response_findings
            if finding.llm_support_status == "unconfirmed" and finding.source_validation_status == "source_valid"
        )
        if failed_batch_count > 0 or unsupported_items or invalid_source_finding_count > 0 or response_unconfirmed_findings or not response_findings:
            validation_status = "warning"
        finish_analysis_run(
            db,
            run,
            status="succeeded",
            validation_status=validation_status,
            output_summary={
                "batch_count": len(batches),
                "processed_batch_count": processed_batch_count,
                "failed_batch_count": failed_batch_count,
                "created_research_finding_count": len(response_findings),
                "corrected_research_finding_count": corrected_finding_count,
                "unconfirmed_research_finding_count": len(response_unconfirmed_findings),
                "source_invalid_research_finding_count": invalid_source_finding_count,
                "unsupported_count": len(unsupported_items),
                "unsupported_items": unsupported_items[:5],
            },
        )
        return AnalysisModuleRunResponse(
            analysis_run_id=run.id,
            module_key="search_findings",
            model=settings.llm_chat_model,
            research_findings=response_findings,
            unconfirmed_research_findings=response_unconfirmed_findings,
            unsupported_items=unsupported_items,
            selected_chunk_ids=[retrieved.chunk.id for retrieved in retrieved_chunks],
            validation_status=validation_status,
        )
    except Exception as exc:
        if run.status == "running":
            finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=str(exc))
        if isinstance(exc, AnalysisModuleError):
            raise
        raise AnalysisModuleError(str(exc)) from exc


def build_search_findings_user_prompt(
    query: str | None,
    retrieved_chunks: list[RetrievedChunk],
    batch_index: int = 1,
    batch_count: int = 1,
    *,
    db: Session | None = None,
) -> str:
    focus_text = query.strip() if isinstance(query, str) and query.strip() else "Nincs külön fókusz."
    return (
        f"QUERY:\n{focus_text}\n\n"
        f"BATCH:\n{batch_index}/{batch_count}\n\n"
        f"SOURCE:\n{build_source_blocks(db, retrieved_chunks)}"
    )


def parse_search_findings_llm_json_object(raw_content: str) -> dict[str, Any]:
    try:
        return parse_llm_json_object(raw_content)
    except AnalysisModuleError as exc:
        recovered = _recover_search_findings_json_fields(raw_content)
        if recovered is None:
            raise exc
        return recovered


def _recover_search_findings_json_fields(raw_content: str) -> dict[str, Any] | None:
    cleaned = raw_content.strip()
    object_start = cleaned.find("{")
    object_end = cleaned.rfind("}")
    if object_start != -1 and object_end > object_start:
        cleaned = cleaned[object_start : object_end + 1]
    item_starts = [match.start() for match in re.finditer(r'"source_label"\s*:', cleaned)]
    if not item_starts:
        return None

    fields = [
        ("source_label", "quote_text"),
        ("quote_text", "title"),
        ("title", "finding_text"),
        ("finding_text", "relevance_reason"),
        ("relevance_reason", "suggested_type"),
        ("suggested_type", "suggested_type_reason"),
    ]
    findings: list[dict[str, Any]] = []
    for index, start in enumerate(item_starts):
        end = item_starts[index + 1] if index + 1 < len(item_starts) else len(cleaned)
        segment = cleaned[start:end]
        item: dict[str, Any] = {}
        for field_name, next_field in fields:
            value = _extract_ordered_json_string_field(segment, field_name, next_field=next_field)
            if value is None:
                return None
            item[field_name] = value
        suggested_type_reason = _extract_final_json_string_field(segment, "suggested_type_reason")
        if suggested_type_reason is None:
            return None
        item["suggested_type_reason"] = suggested_type_reason
        findings.append(item)
    return {"findings": findings}


def _extract_ordered_json_string_field(raw_content: str, field_name: str, *, next_field: str) -> str | None:
    pattern = rf'"{re.escape(field_name)}"\s*:\s*"(.*)"\s*,\s*"{re.escape(next_field)}"\s*:'
    match = re.search(pattern, raw_content, flags=re.DOTALL)
    if match is None:
        return None
    return _decode_json_string_fragment(match.group(1))


def _extract_final_json_string_field(raw_content: str, field_name: str) -> str | None:
    pattern = rf'"{re.escape(field_name)}"\s*:\s*"(.*?)"\s*}}\s*(?:,\s*\{{)?\s*(?:\]\s*}})?\s*$'
    match = re.search(pattern, raw_content.strip(), flags=re.DOTALL)
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


def validate_extracted_findings(
    payload: dict[str, Any],
    retrieved_chunks: list[RetrievedChunk],
    *,
    db: Session | None = None,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    findings_value = payload.get("findings", [])
    if not isinstance(findings_value, list):
        raise AnalysisModuleError("LLM JSON has invalid findings field")

    chunks_by_label = {retrieved.label: retrieved for retrieved in retrieved_chunks}
    valid_findings: list[dict[str, Any]] = []
    unsupported_items: list[str] = []
    unconfirmed_findings: list[dict[str, Any]] = []
    for item in findings_value:
        finding = _validated_finding_item(item, chunks_by_label, llm_support_status="confirmed", db=db)
        if finding is None:
            repaired_finding = _repaired_validated_finding_item(item, chunks_by_label, db=db)
            if repaired_finding is not None:
                valid_findings.append(repaired_finding)
            else:
                invalid_finding = _source_invalid_finding_item(item, chunks_by_label)
                if invalid_finding is not None:
                    valid_findings.append(invalid_finding)
                else:
                    unsupported_items.append(_finding_validation_error(item, chunks_by_label, db=db))
            continue
        valid_findings.append(finding)
    return valid_findings, unsupported_items, unconfirmed_findings


def _finding_validation_error(item: Any, chunks_by_label: dict[str, RetrievedChunk], *, db: Session | None = None) -> str:
    if not isinstance(item, dict):
        return "item: az LLM találat nem objektum"

    title = item.get("title")
    finding_text = item.get("finding_text")
    relevance_reason = item.get("relevance_reason")
    quote_text = item.get("quote_text")
    source_label = item.get("source_label")
    if not isinstance(source_label, str) or source_label.strip() == "":
        return "item: hiányzó vagy érvénytelen source_label"
    if source_label not in chunks_by_label:
        available_labels = ", ".join(chunks_by_label.keys())
        return f"{source_label}: ismeretlen source_label; elérhető címkék: {available_labels}"
    if not all(isinstance(value, str) for value in [title, finding_text, relevance_reason, quote_text]):
        return f"{source_label}: hiányzó vagy érvénytelen kötelező találati mező"
    if title.strip() == "" or finding_text.strip() == "" or relevance_reason.strip() == "" or quote_text.strip() == "":
        return f"{source_label}: üres kötelező találati mező"

    retrieved = chunks_by_label[source_label]
    source_text = read_chunk_text_from_store(db, retrieved.chunk) if db is not None else read_chunk_text(retrieved.chunk)
    if _resolve_quote_text(source_text, quote_text) is None:
        return f"{source_label}: quote_text nem pontos vagy nem található a megadott forrásszövegben: {_debug_text_excerpt(quote_text)}"
    return f"{source_label}: ismeretlen validációs hiba"


def _base_finding_fields(item: Any, chunks_by_label: dict[str, RetrievedChunk]) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    title = item.get("title")
    finding_text = item.get("finding_text")
    suggested_type = item.get("suggested_type", "other")
    suggested_type_reason = item.get("suggested_type_reason")
    relevance_reason = item.get("relevance_reason")
    quote_text = item.get("quote_text")
    source_label = item.get("source_label")
    if suggested_type not in SUPPORTED_FINDING_TYPES:
        suggested_type = "other"
    if not all(isinstance(value, str) for value in [title, finding_text, relevance_reason, quote_text, source_label]):
        return None
    if title.strip() == "" or finding_text.strip() == "" or relevance_reason.strip() == "" or quote_text.strip() == "":
        return None
    retrieved = chunks_by_label.get(source_label)
    if retrieved is None:
        return None
    return {
        "title": title,
        "finding_text": finding_text,
        "suggested_type": suggested_type,
        "suggested_type_reason": suggested_type_reason if isinstance(suggested_type_reason, str) and suggested_type_reason.strip() else None,
        "relevance_reason": relevance_reason,
        "quote_text": quote_text,
        "source_label": source_label,
        "chunk": retrieved.chunk,
        "document_name": retrieved.document_name,
    }


def _repaired_validated_finding_item(
    item: Any,
    chunks_by_label: dict[str, RetrievedChunk],
    *,
    db: Session | None = None,
) -> dict[str, Any] | None:
    base = _base_finding_fields(item, chunks_by_label)
    if base is None:
        return None
    quote_text = base["quote_text"]
    chunk = base["chunk"]
    source_text = read_chunk_text_from_store(db, chunk) if db is not None else read_chunk_text(chunk)
    if _resolve_quote_text(source_text, quote_text) is not None:
        return None
    partial_quote = _resolve_partial_quote_text(source_text, quote_text)
    if partial_quote is None:
        return None
    return {
        "title": base["title"],
        "finding_text": base["finding_text"],
        "suggested_type": base["suggested_type"],
        "suggested_type_reason": base["suggested_type_reason"],
        "relevance_reason": base["relevance_reason"],
        "quote_text": partial_quote,
        "source_label": base["source_label"],
        "chunk": chunk,
        "document_name": base["document_name"],
        "llm_support_status": "unconfirmed",
        "source_validation_status": "source_valid",
    }


def _source_invalid_finding_item(item: Any, chunks_by_label: dict[str, RetrievedChunk]) -> dict[str, Any] | None:
    base = _base_finding_fields(item, chunks_by_label)
    if base is None:
        return None
    return {
        **base,
        "llm_support_status": "unconfirmed",
        "source_validation_status": "source_invalid",
    }


def _validated_finding_item(
    item: Any,
    chunks_by_label: dict[str, RetrievedChunk],
    *,
    llm_support_status: str,
    db: Session | None = None,
) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    title = item.get("title")
    finding_text = item.get("finding_text")
    suggested_type = item.get("suggested_type", "other")
    suggested_type_reason = item.get("suggested_type_reason")
    relevance_reason = item.get("relevance_reason")
    quote_text = item.get("quote_text")
    source_label = item.get("source_label")
    if suggested_type not in SUPPORTED_FINDING_TYPES:
        suggested_type = "other"
    if not all(isinstance(value, str) for value in [title, finding_text, relevance_reason, quote_text, source_label]):
        return None
    if title.strip() == "" or finding_text.strip() == "" or relevance_reason.strip() == "" or quote_text.strip() == "":
        return None
    retrieved = chunks_by_label.get(source_label)
    if retrieved is None:
        return None
    source_text = read_chunk_text_from_store(db, retrieved.chunk) if db is not None else read_chunk_text(retrieved.chunk)
    resolved_quote = _resolve_quote_text(source_text, quote_text)
    if resolved_quote is None:
        return None
    return {
        "title": title,
        "finding_text": finding_text,
        "suggested_type": suggested_type,
        "suggested_type_reason": suggested_type_reason if isinstance(suggested_type_reason, str) and suggested_type_reason.strip() else None,
        "relevance_reason": relevance_reason,
        "quote_text": resolved_quote,
        "source_label": source_label,
        "chunk": retrieved.chunk,
        "document_name": retrieved.document_name,
        "llm_support_status": llm_support_status,
        "source_validation_status": "source_valid",
    }


def _resolve_quote_text(source_text: str, quote_text: str) -> str | None:
    if quote_text in source_text:
        return quote_text
    normalized_quote = " ".join(quote_text.split())
    if normalized_quote == "":
        return None
    if normalized_quote in source_text:
        return normalized_quote
    normalized_source, source_index_map = _normalize_for_quote_lookup(source_text)
    normalized_lookup_quote, _quote_index_map = _normalize_for_quote_lookup(quote_text)
    if len(normalized_lookup_quote) < 8:
        return None
    normalized_start = normalized_source.casefold().find(normalized_lookup_quote.casefold())
    if normalized_start < 0:
        return None
    normalized_end = normalized_start + len(normalized_lookup_quote) - 1
    return source_text[source_index_map[normalized_start] : source_index_map[normalized_end] + 1]


def _resolve_partial_quote_text(source_text: str, quote_text: str) -> str | None:
    matched_parts: list[str] = []
    for part in _quote_candidate_parts(quote_text):
        if _normalized_length(part) < 12:
            continue
        resolved_part = _resolve_quote_text(source_text, part)
        if resolved_part is not None:
            matched_parts.append(resolved_part)

    if not matched_parts:
        return None
    strong_parts = [part for part in matched_parts if _normalized_length(part) >= 30]
    if strong_parts:
        return max(strong_parts, key=_normalized_length)
    if len(matched_parts) >= 2:
        return max(matched_parts, key=_normalized_length)
    return None


def _quote_candidate_parts(quote_text: str) -> list[str]:
    rough_parts = re.split(r"\.\.\.|…|\n+", quote_text)
    parts: list[str] = []
    for rough_part in rough_parts:
        parts.extend(re.split(r"(?<=[.!?])\s+", rough_part))
    return [part.strip(" \t\r\n\"'„”") for part in parts if part.strip(" \t\r\n\"'„”")]


def _normalized_length(value: str) -> int:
    normalized_value, _index_map = _normalize_for_quote_lookup(value)
    return len(normalized_value)


def _normalize_for_quote_lookup(value: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    index_map: list[int] = []
    for index, char in enumerate(value):
        if char.isspace():
            continue
        chars.append(char)
        index_map.append(index)
    return "".join(chars), index_map


def _debug_text_excerpt(value: str, limit: int = 160) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) > limit:
        collapsed = f"{collapsed[:limit]}..."
    return f'"{collapsed}"'
