from dataclasses import dataclass
from datetime import UTC, datetime
import json
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import DocumentModel, DocumentPageModel
from app.models.document_processing import DocumentProcessingItemModel, FullDocumentAnswerModel
from app.schemas.full_document_processing import (
    DocumentProcessingItemRead,
    FullDocumentAnswerRead,
    FullDocumentProcessingRunRequest,
    FullDocumentProcessingRunResponse,
)
from app.services.analysis_module_common import parse_llm_json_object
from app.services.analysis_runs import add_analysis_run_input, add_analysis_run_output, finish_analysis_run, start_analysis_run
from app.services.llm import LLMChatMessage, LMStudioNativeProvider
from app.services.text_store import read_page_text_from_store


class FullDocumentProcessingError(ValueError):
    pass


class FullDocumentProcessingNotFoundError(FullDocumentProcessingError):
    pass


class FullDocumentProcessingValidationError(FullDocumentProcessingError):
    pass


@dataclass(frozen=True)
class FullDocumentProcessingProfile:
    key: str
    label: str
    description: str
    item_kinds: tuple[str, ...]


PROFILES: tuple[FullDocumentProcessingProfile, ...] = (
    FullDocumentProcessingProfile(
        key="person_search_seeds",
        label="Személykeresési fókuszok",
        description="Teljes iratból kinyert személyek és személyhez köthető keresési fókuszok előállítása.",
        item_kinds=("person",),
    ),
    FullDocumentProcessingProfile(
        key="free_document_question",
        label="Szabad iratkérdés",
        description="Kérdés megválaszolása a kijelölt irat megadott oldalai alapján.",
        item_kinds=(),
    ),
)

PROFILE_KEYS = {profile.key for profile in PROFILES}
WORK_STATUSES = {"active", "set_aside", "converted", "deleted"}
USER_SETTABLE_WORK_STATUSES = {"active", "set_aside", "deleted"}
FULL_DOCUMENT_PROCESSING_MAX_OUTPUT_TOKENS = 9000
FULL_DOCUMENT_FREE_QUESTION_MAX_OUTPUT_TOKENS = None
FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT = """Forráshű teljes iratfeldolgozó komponens vagy.

Alapelvek:
- A SOURCE az egyetlen igazságforrás.
- Magyar forrásiratokkal dolgozol.
- Ne használj külső tudást, ne pótolj hiányzó adatot, ne feltételezz, ne következtess.
- Ne állapíts meg bűnösséget, felelősséget, jogi minősítést, kockázatot vagy személyes hibát.

Feladat:
- Add vissza JSON formában a SOURCE-ban szereplő személyeket.
- Minden szereplőt a hozzá tartozó display_label értéke határoz meg.
- A display_label értéke kizárólag és pontosan a forrásban szereplő névalak legyen.
- Minden szereplő kizárólag egyszer szerepelhet az items listában, még akkor is ha több oldalon is szerepel.

Mezőszabályok:
- Az item_kind értéke person legyen.
- A recommended_search_focus rövid keresési kifejezés legyen: display_label + 1-4 forrásbeli szó, amely a személy saját szerepét, címét, foglalkozását vagy jelzőjét azonosítja.
- A recommended_search_focus nem mondat, nem összefoglaló, nem idézet és nem felsorolás; ne tegyél bele töltelékszöveget vagy felesleges kapcsolati neveket.
- A display_label és recommended_search_focus értékekben őrizd meg a SOURCE szerinti írásmódot, beleértve a " és ' jeleket is. JSON stringben szükség esetén csak escape-eld őket, ne cseréld át másik idézőjelre.
- A source_label megadása minden items elemben kötelező. Értéke csak page_1, page_2, page_3 stb. alakú lehet, a SOURCE-ban látható page címkék közül.
- Minden szereplőhöz annak az oldalnak a source_label értékét add meg, ahol a display_label névalak szerepel.

JSON szabályok:
- Csak érvényes JSON objektumot adhatsz vissza.
- Ne írj magyarázatot, markdown blokkot vagy JSON-on kívüli szöveget.
- A JSON objektumok minden mezőneve dupla idézőjelben legyen.
- A JSON stringeken belüli dupla idézőjeleket escape-eld.

Elvárt JSON forma:
{"items":[{"item_kind":"person","display_label":"...","recommended_search_focus":"...","source_label":"page_1"}]}
Ha nincs használható elem:
{"items":[]}
"""

FULL_DOCUMENT_FREE_QUESTION_SYSTEM_PROMPT = """Forráshű iratválaszoló komponens vagy.

Alapelvek:
- A SOURCE az egyetlen igazságforrás.
- A QUERY a felhasználó kérdése.
- Csak a SOURCE alapján válaszolhatsz.
- Ne használj külső tudást, ne pótolj hiányzó adatot, ne feltételezz.
- Ha a SOURCE nem ad elég alapot a válaszhoz, mondd ki.
- Ne állapíts meg bűnösséget, felelősséget, jogi minősítést, kockázatot vagy személyes hibát.
- Ne tegyél kész tényként olyan állítást, amelyet a SOURCE csak feltételezésként, következtetésként vagy lehetőségként fogalmaz meg.

Feladat:
- Válaszolj magyar nyelven a QUERY-re a kijelölt iratoldalak alapján.
- A válasz lehet részletes, ha a SOURCE ezt alátámasztja.
- Őrizd meg a SOURCE bizonyossági szintjét.

JSON mezők:
- insufficient_source: boolean. true, ha a SOURCE nem ad elég alapot érdemi válaszhoz, különben false.
- source_summary: legfeljebb egy rövid mondat arról, mely oldalak vagy forrásrészek adják a válasz alapját. Ha nem ad hozzá hasznos információt, legyen üres string.
- answer_text: a QUERY-re adott forráshű válasz.

JSON szabályok:
- Csak érvényes JSON objektumot adhatsz vissza.
- Ne írj magyarázatot, markdown blokkot vagy JSON-on kívüli szöveget.
- A JSON objektumok minden mezőneve dupla idézőjelben legyen.
- A JSON stringeken belüli dupla idézőjeleket escape-eld.
- Sortörést csak JSON escape-ként használhatsz: \\n.

Elvárt JSON forma:
{"insufficient_source":false,"source_summary":"...","answer_text":"..."}
"""

def list_profiles() -> list[FullDocumentProcessingProfile]:
    return list(PROFILES)


def run_full_document_processing(
    db: Session,
    *,
    case_id: UUID,
    document_id: UUID,
    payload: FullDocumentProcessingRunRequest,
) -> FullDocumentProcessingRunResponse:
    profile = _profile_by_key(payload.profile_key)
    document = _ensure_document_belongs_to_case(db, case_id=case_id, document_id=document_id)
    if document.lifecycle_status != "active":
        raise FullDocumentProcessingValidationError("Csak aktív irat dolgozható fel teljes iratfeldolgozással")

    pages = _current_document_pages(db, case_id=case_id, document_id=document_id)
    page_start, page_end = _validate_page_range(pages, payload.page_start, payload.page_end)
    selected_pages = [page for page in pages if page_start <= page.page_number <= page_end]
    page_sources = _page_sources(db, selected_pages)
    if not page_sources:
        raise FullDocumentProcessingValidationError("Az iratnak nincs feldolgozható aktuális szövegrétege")
    if profile.key == "free_document_question":
        return _run_full_document_free_question(
            db,
            case_id=case_id,
            document_id=document_id,
            document=document,
            payload=payload,
            page_start=page_start,
            page_end=page_end,
            page_sources=page_sources,
        )

    settings = get_settings()
    run = start_analysis_run(
        db,
        case_id,
        "full_document_processing",
        provider_type="lm_studio_native",
        model_name=settings.llm_chat_model,
        input_parameters={
            "document_id": str(document_id),
            "profile_key": payload.profile_key,
            "page_start": page_start,
            "page_end": page_end,
        },
        prompt_template_name="full_document_processing_v1",
        prompt_template_version="1",
        output_schema_name="document_processing_items",
        output_schema_version="1",
        retrieval_strategy="current_document_pages_v1",
        raw_prompt_text=FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT,
    )
    try:
        add_analysis_run_input(
            db,
            run.id,
            "document",
            0,
            document_id=document.id,
            payload_json={
                "profile_key": payload.profile_key,
                "original_filename": document.original_filename,
                "page_start": page_start,
                "page_end": page_end,
                "selected_page_count": len(page_sources),
            },
        )
        for index, page_source in enumerate(page_sources, start=1):
            add_analysis_run_input(
                db,
                run.id,
                "page",
                index,
                document_id=document.id,
                page_id=page_source["page_id"],
                payload_json={"source_label": page_source["source_label"], "text_char_count": len(page_source["text"])},
            )

        created_items: list[DocumentProcessingItemModel] = []
        unsupported_items: list[str] = []
        provider = LMStudioNativeProvider(settings)
        prompt = build_full_document_processing_user_prompt(
            profile=profile,
            document=document,
            page_sources=page_sources,
        )
        try:
            completion = provider.chat_completion(
                settings.llm_chat_model,
                [
                    LLMChatMessage(role="system", content=FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT),
                    LLMChatMessage(role="user", content=prompt),
                ],
                temperature=0.1,
                max_tokens=FULL_DOCUMENT_PROCESSING_MAX_OUTPUT_TOKENS,
            )
            parsed = parse_full_document_processing_llm_json_object(completion.content)
            valid_items, unsupported_items = validate_full_document_processing_payload(parsed, profile, page_sources)
        except Exception as exc:
            unsupported_items.append(f"LLM válasz feldolgozási hiba: {exc}")
            valid_items = []

        for valid_item in valid_items:
            persisted_item = _create_document_processing_item(
                db,
                case_id=case_id,
                document_id=document_id,
                analysis_run_id=run.id,
                profile_key=profile.key,
                valid_item=valid_item,
            )
            add_analysis_run_output(db, run.id, "document_processing_item", persisted_item.id, len(created_items))
            created_items.append(persisted_item)

        validation_status = "passed" if created_items and not unsupported_items else "warning" if created_items else "failed"
        status = "succeeded" if created_items else "failed"
        failure_detail = unsupported_items[0] if unsupported_items else "nincs validált elem"
        error_message = None if created_items else f"A teljes iratfeldolgozás nem hozott forrással validált elemet: {failure_detail}"
        finish_analysis_run(
            db,
            run,
            status=status,
            validation_status=validation_status,
            error_message=error_message,
            output_summary={
                "created_item_count": len(created_items),
                "unsupported_count": len(unsupported_items),
                "profile_key": profile.key,
                "document_id": str(document_id),
                "page_start": page_start,
                "page_end": page_end,
                "unsupported_items": unsupported_items[:10],
            },
        )
        for item in created_items:
            db.refresh(item)
        return FullDocumentProcessingRunResponse(
            analysis_run_id=run.id,
            document_id=document_id,
            profile_key=profile.key,
            created_item_count=len(created_items),
            unsupported_count=len(unsupported_items),
            validation_status=validation_status,
            items=document_processing_item_reads(created_items),
            unsupported_items=unsupported_items,
        )
    except Exception as exc:
        if run.status == "running":
            finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=str(exc))
        if isinstance(exc, FullDocumentProcessingError):
            raise
        raise FullDocumentProcessingValidationError(str(exc)) from exc


def _run_full_document_free_question(
    db: Session,
    *,
    case_id: UUID,
    document_id: UUID,
    document: DocumentModel,
    payload: FullDocumentProcessingRunRequest,
    page_start: int,
    page_end: int,
    page_sources: list[dict[str, Any]],
) -> FullDocumentProcessingRunResponse:
    question_text = (payload.question_text or "").strip()
    if not question_text:
        raise FullDocumentProcessingValidationError("A szabad iratkérdés profilhoz kérdést kell megadni")

    settings = get_settings()
    prompt_template_name = "full_document_free_question_v1"
    prompt_template_version = "1"
    run = start_analysis_run(
        db,
        case_id,
        "full_document_processing",
        provider_type="lm_studio_native",
        model_name=settings.llm_chat_model,
        input_parameters={
            "document_id": str(document_id),
            "profile_key": payload.profile_key,
            "page_start": page_start,
            "page_end": page_end,
            "question_text": question_text,
        },
        prompt_template_name=prompt_template_name,
        prompt_template_version=prompt_template_version,
        output_schema_name="full_document_answer",
        output_schema_version="1",
        retrieval_strategy="current_document_pages_v1",
        raw_prompt_text=FULL_DOCUMENT_FREE_QUESTION_SYSTEM_PROMPT,
    )
    try:
        add_analysis_run_input(
            db,
            run.id,
            "document",
            0,
            document_id=document.id,
            payload_json={
                "profile_key": payload.profile_key,
                "original_filename": document.original_filename,
                "page_start": page_start,
                "page_end": page_end,
                "selected_page_count": len(page_sources),
            },
        )
        add_analysis_run_input(db, run.id, "query_text", 1, payload_json={"query": question_text})
        for index, page_source in enumerate(page_sources, start=2):
            add_analysis_run_input(
                db,
                run.id,
                "page",
                index,
                document_id=document.id,
                page_id=page_source["page_id"],
                payload_json={"source_label": page_source["source_label"], "text_char_count": len(page_source["text"])},
            )

        completion = LMStudioNativeProvider(settings).chat_completion(
            settings.llm_chat_model,
            [
                LLMChatMessage(role="system", content=FULL_DOCUMENT_FREE_QUESTION_SYSTEM_PROMPT),
                LLMChatMessage(
                    role="user",
                    content=build_full_document_free_question_user_prompt(
                        document=document,
                        question_text=question_text,
                        page_sources=page_sources,
                    ),
                ),
            ],
            temperature=0.1,
            max_tokens=FULL_DOCUMENT_FREE_QUESTION_MAX_OUTPUT_TOKENS,
        )
        parsed = parse_full_document_free_question_llm_json_object(completion.content)
        answer_payload = validate_full_document_free_question_payload(parsed)
        source_summary = answer_payload["source_summary"] or _default_free_question_source_summary(document, page_start, page_end)
        now = datetime.now(UTC)
        answer = FullDocumentAnswerModel(
            case_id=case_id,
            document_id=document_id,
            analysis_run_id=run.id,
            profile_key="free_document_question",
            question_text=question_text,
            answer_text=answer_payload["answer_text"],
            source_summary=source_summary,
            page_start=page_start,
            page_end=page_end,
            source_page_count=len(page_sources),
            source_character_count=sum(len(page_source["text"]) for page_source in page_sources),
            model_name=settings.llm_chat_model,
            prompt_template_name=prompt_template_name,
            prompt_template_version=prompt_template_version,
            answer_status="active",
            created_at=now,
            updated_at=now,
        )
        db.add(answer)
        db.flush()
        add_analysis_run_output(db, run.id, "full_document_answer", answer.id, 0)
        validation_status = "warning" if answer_payload["insufficient_source"] else "passed"
        finish_analysis_run(
            db,
            run,
            status="succeeded",
            validation_status=validation_status,
            output_summary={
                "profile_key": "free_document_question",
                "document_id": str(document_id),
                "page_start": page_start,
                "page_end": page_end,
                "question_text": question_text,
                "answer_id": str(answer.id),
                "insufficient_source": answer_payload["insufficient_source"],
                "source_page_count": len(page_sources),
                "source_character_count": answer.source_character_count,
            },
        )
        db.commit()
        db.refresh(answer)
        return FullDocumentProcessingRunResponse(
            analysis_run_id=run.id,
            document_id=document_id,
            profile_key="free_document_question",
            created_item_count=0,
            unsupported_count=0,
            validation_status=validation_status,
            items=[],
            unsupported_items=[],
            answer=FullDocumentAnswerRead.model_validate(answer),
        )
    except Exception as exc:
        if run.status == "running":
            finish_analysis_run(db, run, status="failed", validation_status="failed", error_message=str(exc))
        if isinstance(exc, FullDocumentProcessingError):
            raise
        raise FullDocumentProcessingValidationError(str(exc)) from exc


def list_document_processing_items(
    db: Session,
    *,
    case_id: UUID,
    document_id: UUID,
    profile_key: str | None = None,
    work_status: str | None = None,
    item_kind: str | None = None,
    search: str | None = None,
) -> list[DocumentProcessingItemModel]:
    _ensure_document_belongs_to_case(db, case_id=case_id, document_id=document_id)
    if profile_key is not None and profile_key not in PROFILE_KEYS:
        raise FullDocumentProcessingValidationError("Ismeretlen teljes iratfeldolgozási profil")
    if work_status is not None and work_status not in WORK_STATUSES:
        raise FullDocumentProcessingValidationError("Ismeretlen munkalista-állapot")

    statement = select(DocumentProcessingItemModel).where(
        DocumentProcessingItemModel.case_id == case_id,
        DocumentProcessingItemModel.document_id == document_id,
    )
    if profile_key is not None:
        statement = statement.where(DocumentProcessingItemModel.profile_key == profile_key)
    if work_status is not None:
        statement = statement.where(DocumentProcessingItemModel.work_status == work_status)
    if item_kind is not None:
        statement = statement.where(DocumentProcessingItemModel.item_kind == item_kind)
    if search is not None and search.strip():
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            DocumentProcessingItemModel.display_label.ilike(pattern)
            | DocumentProcessingItemModel.short_description.ilike(pattern)
            | DocumentProcessingItemModel.recommended_search_focus.ilike(pattern)
        )
    statement = statement.order_by(DocumentProcessingItemModel.created_at.desc(), DocumentProcessingItemModel.display_label.asc())
    return list(db.execute(statement).scalars())


def document_processing_item_reads(items: list[DocumentProcessingItemModel]) -> list[DocumentProcessingItemRead]:
    repeated_keys = _repeated_item_keys(items)
    reads: list[DocumentProcessingItemRead] = []
    for item in items:
        read = DocumentProcessingItemRead.model_validate(item)
        read.occurrence_status = "repeated" if _dedupe_key_for_item(item.item_kind, item.display_label, {}) in repeated_keys else "unique"
        reads.append(read)
    return reads


def list_full_document_answers(
    db: Session,
    *,
    case_id: UUID,
    document_id: UUID | None = None,
    answer_status: str = "active",
) -> list[FullDocumentAnswerModel]:
    if answer_status not in {"active", "deleted"}:
        raise FullDocumentProcessingValidationError("Ismeretlen iratválasz-állapot")
    statement = select(FullDocumentAnswerModel).where(
        FullDocumentAnswerModel.case_id == case_id,
        FullDocumentAnswerModel.answer_status == answer_status,
    )
    if document_id is not None:
        _ensure_document_belongs_to_case(db, case_id=case_id, document_id=document_id)
        statement = statement.where(FullDocumentAnswerModel.document_id == document_id)
    statement = statement.order_by(FullDocumentAnswerModel.created_at.desc())
    return list(db.execute(statement).scalars())


def get_full_document_answer(db: Session, *, case_id: UUID, answer_id: UUID) -> FullDocumentAnswerModel:
    answer = db.get(FullDocumentAnswerModel, answer_id)
    if answer is None or answer.case_id != case_id:
        raise FullDocumentProcessingNotFoundError("Az iratválasz nem található")
    return answer


def delete_full_document_answer(db: Session, *, case_id: UUID, answer_id: UUID) -> None:
    answer = get_full_document_answer(db, case_id=case_id, answer_id=answer_id)
    if answer.answer_status != "deleted":
        answer.answer_status = "deleted"
        answer.updated_at = datetime.now(UTC)
        db.add(answer)
        db.commit()


def get_document_processing_item(db: Session, *, case_id: UUID, item_id: UUID) -> DocumentProcessingItemModel:
    item = db.get(DocumentProcessingItemModel, item_id)
    if item is None or item.case_id != case_id:
        raise FullDocumentProcessingNotFoundError("A teljes iratfeldolgozási elem nem található")
    return item


def update_document_processing_item_status(
    db: Session,
    *,
    case_id: UUID,
    item_id: UUID,
    work_status: str,
) -> DocumentProcessingItemModel:
    if work_status not in USER_SETTABLE_WORK_STATUSES:
        raise FullDocumentProcessingValidationError("Ez a munkalista-állapot ezen az útvonalon nem állítható")
    item = get_document_processing_item(db, case_id=case_id, item_id=item_id)
    if item.work_status == "converted":
        raise FullDocumentProcessingValidationError("Átalakított teljes iratfeldolgozási elem állapota itt nem módosítható")
    item.work_status = work_status
    item.updated_at = datetime.now(UTC)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def bulk_delete_document_processing_items(db: Session, *, case_id: UUID, item_ids: list[UUID]) -> int:
    if not item_ids:
        return 0
    unique_item_ids = list(dict.fromkeys(item_ids))
    items = list(
        db.execute(
            select(DocumentProcessingItemModel).where(
                DocumentProcessingItemModel.case_id == case_id,
                DocumentProcessingItemModel.id.in_(unique_item_ids),
            )
        ).scalars()
    )
    if len(items) != len(unique_item_ids):
        raise FullDocumentProcessingNotFoundError("Egy vagy több teljes iratfeldolgozási elem nem található")
    now = datetime.now(UTC)
    deleted_count = 0
    for item in items:
        if item.work_status == "converted":
            raise FullDocumentProcessingValidationError("Átalakított teljes iratfeldolgozási elem nem törölhető innen")
        if item.work_status != "deleted":
            item.work_status = "deleted"
            item.updated_at = now
            db.add(item)
            deleted_count += 1
    db.commit()
    return deleted_count


def build_full_document_processing_user_prompt(
    *,
    profile: FullDocumentProcessingProfile,
    document: DocumentModel,
    page_sources: list[dict[str, Any]],
) -> str:
    source_pages = "\n\n".join(
        f"{page_source['source_label']}:\n"
        f"document_id: {page_source['document_id']}\n"
        f"page_number: {page_source['page_number']}\n"
        f"text:\n{page_source['text']}"
        for page_source in page_sources
    )
    return f"""DOCUMENT:
{document.original_filename}

PROFILE:
{profile.key} - {profile.description}

SOURCE:
{source_pages}"""


def build_full_document_free_question_user_prompt(
    *,
    document: DocumentModel,
    question_text: str,
    page_sources: list[dict[str, Any]],
) -> str:
    source_pages = "\n\n".join(
        f"{page_source['source_label']}:\n"
        f"document_id: {page_source['document_id']}\n"
        f"page_number: {page_source['page_number']}\n"
        f"text:\n{page_source['text']}"
        for page_source in page_sources
    )
    return f"""DOCUMENT:
{document.original_filename}

QUERY:
{question_text}

SOURCE:
{source_pages}"""


def parse_full_document_processing_llm_json_object(raw_content: str) -> dict[str, Any]:
    try:
        return parse_llm_json_object(raw_content)
    except Exception as exc:
        recovered = _recover_full_document_processing_json_fields(raw_content)
        if recovered is None:
            raise exc
        return recovered


def parse_full_document_free_question_llm_json_object(raw_content: str) -> dict[str, Any]:
    try:
        return parse_llm_json_object(raw_content)
    except Exception as exc:
        recovered = _recover_full_document_free_question_json_fields(raw_content)
        if recovered is None:
            raise exc
        return recovered


def validate_full_document_free_question_payload(payload: dict[str, Any]) -> dict[str, Any]:
    answer_text = _clean_string(payload.get("answer_text"))
    if answer_text is None:
        raise FullDocumentProcessingValidationError("A szabad iratkérdés LLM válasz nem tartalmaz answer_text mezőt")
    insufficient_source = _coerce_bool(payload.get("insufficient_source", False))
    if insufficient_source is None:
        insufficient_source = False
    return {
        "answer_text": answer_text,
        "source_summary": _clean_string(payload.get("source_summary")) or "",
        "insufficient_source": insufficient_source,
    }


def _recover_full_document_free_question_json_fields(raw_content: str) -> dict[str, Any] | None:
    cleaned = raw_content.strip()
    object_start = cleaned.find("{")
    object_end = cleaned.rfind("}")
    if object_start != -1:
        cleaned = cleaned[object_start : object_end + 1] if object_end > object_start else cleaned[object_start:]
    insufficient_source = _extract_json_bool_field(cleaned, "insufficient_source")
    source_summary = _extract_json_string_field_any(cleaned, "source_summary", next_fields=["answer_text"]) or ""
    answer_text = _extract_json_string_field_any(cleaned, "answer_text", next_fields=[])
    if answer_text is None:
        return None
    return {
        "insufficient_source": False if insufficient_source is None else insufficient_source,
        "source_summary": source_summary,
        "answer_text": answer_text,
    }


def _extract_json_string_field_any(raw_content: str, field_name: str, *, next_fields: list[str]) -> str | None:
    if next_fields:
        next_pattern = "|".join(re.escape(next_field) for next_field in next_fields)
        pattern = rf'"{re.escape(field_name)}"\s*:\s*"(.*?)"\s*,\s*"({next_pattern})"\s*:'
    else:
        pattern = rf'"{re.escape(field_name)}"\s*:\s*"(.*)"\s*(?:}})?\s*$'
    match = re.search(pattern, raw_content, flags=re.DOTALL)
    if match is None:
        return None
    return _decode_json_string_fragment(match.group(1))


def _extract_json_bool_field(raw_content: str, field_name: str) -> bool | None:
    pattern = rf'"{re.escape(field_name)}"\s*:\s*(true|false|"true"|"false"|0|1|"0"|"1")'
    match = re.search(pattern, raw_content, flags=re.IGNORECASE)
    if match is None:
        return None
    return _coerce_bool(match.group(1).strip('"'))


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "igen", "yes"}:
            return True
        if normalized in {"false", "0", "nem", "no"}:
            return False
    return None


def _default_free_question_source_summary(document: DocumentModel, page_start: int, page_end: int) -> str:
    if page_start == page_end:
        return f"Forrás: {document.original_filename}, {page_start}. oldal."
    return f"Forrás: {document.original_filename}, {page_start}-{page_end}. oldal."


def _recover_full_document_processing_json_fields(raw_content: str) -> dict[str, Any] | None:
    cleaned = raw_content.strip()
    object_start = cleaned.find("{")
    object_end = cleaned.rfind("}")
    if object_start != -1 and object_end > object_start:
        cleaned = cleaned[object_start : object_end + 1]
    item_starts = [match.start() for match in re.finditer(r'"item_kind"\s*:', cleaned)]
    if not item_starts:
        return None

    fields = [
        ("item_kind", "display_label"),
        ("display_label", "recommended_search_focus"),
        ("recommended_search_focus", "source_label"),
    ]
    items: list[dict[str, Any]] = []
    for index, start in enumerate(item_starts):
        end = item_starts[index + 1] if index + 1 < len(item_starts) else len(cleaned)
        segment = cleaned[start:end]
        item: dict[str, Any] = {}
        for field_name, next_field in fields:
            value = _extract_ordered_json_string_field(segment, field_name, next_field=next_field)
            if value is None:
                return None
            item[field_name] = value
        source_label = _extract_final_json_string_field(segment, "source_label")
        if source_label is None:
            return None
        item["source_label"] = source_label
        items.append(item)
    return {"items": items}


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


def validate_full_document_processing_payload(
    payload: dict[str, Any],
    profile: FullDocumentProcessingProfile,
    page_sources: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    raw_items = payload.get("items", [])
    unsupported_items = _string_list(payload.get("unsupported_items", []))
    if not isinstance(raw_items, list):
        raise FullDocumentProcessingValidationError("LLM output items must be an array")

    page_by_label = {page_source["source_label"]: page_source for page_source in page_sources}
    valid_items: list[dict[str, Any]] = []
    for index, raw_item in enumerate(raw_items, start=1):
        if not isinstance(raw_item, dict):
            unsupported_items.append(f"item_{index}: az elem nem objektum")
            continue
        item_kind = _clean_string(raw_item.get("item_kind"))
        display_label = _clean_string(raw_item.get("display_label"))
        if item_kind not in profile.item_kinds:
            unsupported_items.append(f"item_{index}: nem engedélyezett elemtípus")
            continue
        if display_label is None:
            unsupported_items.append(f"item_{index}: hiányzó címke")
            continue

        valid_evidence = _build_source_evidence_from_item(raw_item, display_label, page_by_label)
        source_supported_details = _object_list(raw_item.get("source_supported_details", []))
        if valid_evidence is None:
            validation_message = f"{display_label}: a név nem található a kiválasztott forrásoldalakon"
            unsupported_items.append(validation_message)
            source_supported_details.append(
                {
                    "validation_status": "unconfirmed",
                    "validation_message": validation_message,
                    "llm_source_label": _source_label_from_item(raw_item),
                }
            )

        valid_items.append(
            {
                "item_kind": item_kind,
                "display_label": display_label,
                "short_description": _clean_string(raw_item.get("short_description")),
                "mentioned_forms": _string_list(raw_item.get("mentioned_forms", [])),
                "source_supported_details": source_supported_details,
                "relationships": _object_list(raw_item.get("relationships", [])),
                "recommended_search_focus": _search_focus_from_item(raw_item, display_label),
                "alternative_search_focuses": _string_list(raw_item.get("alternative_search_focuses", [])),
                "source_evidence": valid_evidence or [],
            }
        )
    return valid_items, unsupported_items


def _ensure_document_belongs_to_case(db: Session, *, case_id: UUID, document_id: UUID) -> DocumentModel:
    document = db.get(DocumentModel, document_id)
    if document is None or document.case_id != case_id:
        raise FullDocumentProcessingNotFoundError("Az irat nem található ebben az ügyben")
    return document


def _profile_by_key(profile_key: str) -> FullDocumentProcessingProfile:
    for profile in PROFILES:
        if profile.key == profile_key:
            return profile
    raise FullDocumentProcessingValidationError("Ismeretlen teljes iratfeldolgozási profil")


def _current_document_pages(db: Session, *, case_id: UUID, document_id: UUID) -> list[DocumentPageModel]:
    return list(
        db.execute(
            select(DocumentPageModel)
            .where(
                DocumentPageModel.case_id == case_id,
                DocumentPageModel.document_id == document_id,
                DocumentPageModel.is_current.is_(True),
            )
            .order_by(DocumentPageModel.page_number.asc())
        ).scalars()
    )


def _page_sources(db: Session, pages: list[DocumentPageModel]) -> list[dict[str, Any]]:
    page_sources: list[dict[str, Any]] = []
    for page in pages:
        text = read_page_text_from_store(db, page)
        if not text.strip():
            continue
        page_sources.append(
            {
                "source_label": f"page_{page.page_number}",
                "case_id": page.case_id,
                "document_id": page.document_id,
                "page_id": page.id,
                "page_number": page.page_number,
                "text": text,
            }
        )
    return page_sources


def _validate_page_range(pages: list[DocumentPageModel], requested_start: int | None, requested_end: int | None) -> tuple[int, int]:
    if not pages:
        raise FullDocumentProcessingValidationError("Az iratnak nincs aktuális oldalszövege")
    min_page = min(page.page_number for page in pages)
    max_page = max(page.page_number for page in pages)
    page_start = requested_start if requested_start is not None else min_page
    page_end = requested_end if requested_end is not None else max_page
    if page_start < min_page or page_end > max_page:
        raise FullDocumentProcessingValidationError(f"Az oldaltartomány csak {min_page} és {max_page} között lehet")
    if page_start > page_end:
        raise FullDocumentProcessingValidationError("Az első oldal nem lehet nagyobb az utolsó oldalnál")
    return page_start, page_end


def _create_document_processing_item(
    db: Session,
    *,
    case_id: UUID,
    document_id: UUID,
    analysis_run_id: UUID,
    profile_key: str,
    valid_item: dict[str, Any],
) -> DocumentProcessingItemModel:
    now = datetime.now(UTC)
    item = DocumentProcessingItemModel(
        case_id=case_id,
        document_id=document_id,
        analysis_run_id=analysis_run_id,
        profile_key=profile_key,
        item_kind=valid_item["item_kind"],
        display_label=valid_item["display_label"],
        short_description=valid_item["short_description"],
        mentioned_forms_json=valid_item["mentioned_forms"],
        source_supported_details_json=valid_item["source_supported_details"],
        relationships_json=valid_item["relationships"],
        recommended_search_focus=valid_item["recommended_search_focus"],
        alternative_search_focuses_json=valid_item["alternative_search_focuses"],
        source_evidence_json=valid_item["source_evidence"],
        work_status="active",
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    db.flush()
    return item


def _clean_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _find_quote_span(source_text: str, quote_text: str) -> tuple[int, int] | None:
    quote_start = source_text.find(quote_text)
    if quote_start >= 0:
        return quote_start, quote_start + len(quote_text)

    normalized_source, source_index_map = _normalize_for_quote_lookup(source_text)
    normalized_quote, _quote_index_map = _normalize_for_quote_lookup(quote_text)
    if len(normalized_quote) < 8:
        return None
    normalized_start = normalized_source.find(normalized_quote)
    if normalized_start < 0:
        return None
    normalized_end = normalized_start + len(normalized_quote) - 1
    return source_index_map[normalized_start], source_index_map[normalized_end] + 1


def _build_source_evidence_from_item(
    raw_item: dict[str, Any],
    display_label: str,
    page_by_label: dict[str, dict[str, Any]],
) -> list[dict[str, Any]] | None:
    source_label = _source_label_from_item(raw_item)
    page_source = page_by_label.get(source_label or "")
    label_candidates = _label_lookup_candidates(display_label, _string_list(raw_item.get("mentioned_forms", [])))
    quote_span: tuple[int, int] | None = None
    if page_source is not None:
        quote_span = _find_first_label_span(page_source["text"], label_candidates)
    if quote_span is None:
        page_source, quote_span = _find_label_on_any_page(page_by_label, label_candidates)
    if quote_span is None:
        return None

    quote_start, quote_end = _expand_span_to_sentence(page_source["text"], quote_span)
    exact_quote_text = page_source["text"][quote_start:quote_end]
    return [
        {
            "source_label": page_source["source_label"],
            "quote_text": exact_quote_text,
            "document_id": str(page_source["document_id"]),
            "page_id": str(page_source["page_id"]),
            "page_number": page_source["page_number"],
            "quote_char_start": quote_start,
            "quote_char_end": quote_end,
        }
    ]


def _expand_span_to_sentence(source_text: str, span: tuple[int, int]) -> tuple[int, int]:
    start, end = span
    sentence_start = _sentence_start_before(source_text, start)
    sentence_end = _sentence_end_after(source_text, end)
    return _trim_span_whitespace(source_text, sentence_start, sentence_end)


def _sentence_start_before(source_text: str, index: int) -> int:
    paragraph_break = source_text.rfind("\n\n", 0, index)
    start_limit = paragraph_break + 2 if paragraph_break >= 0 else 0
    for position in range(index - 1, start_limit - 1, -1):
        char = source_text[position]
        if char in "!?":
            return position + 1
        if char == "." and _is_sentence_period(source_text, position):
            return position + 1
    return start_limit


def _sentence_end_after(source_text: str, index: int) -> int:
    paragraph_break = source_text.find("\n\n", index)
    end_limit = paragraph_break if paragraph_break >= 0 else len(source_text)
    for position in range(index, end_limit):
        char = source_text[position]
        if char in "!?":
            return position + 1
        if char == "." and _is_sentence_period(source_text, position):
            return position + 1
    return end_limit


def _is_sentence_period(source_text: str, position: int) -> bool:
    token_start = position - 1
    while token_start >= 0 and source_text[token_start].isalpha():
        token_start -= 1
    token = source_text[token_start + 1 : position].casefold()
    if token in {"dr", "ifj", "id", "özv", "stb", "pl", "kb", "u", "ti", "sz"}:
        return False
    return True


def _trim_span_whitespace(source_text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and source_text[start].isspace():
        start += 1
    while end > start and source_text[end - 1].isspace():
        end -= 1
    return start, end


def _find_label_on_any_page(
    page_by_label: dict[str, dict[str, Any]],
    label_candidates: list[str],
) -> tuple[dict[str, Any] | None, tuple[int, int] | None]:
    for page_source in page_by_label.values():
        quote_span = _find_first_label_span(page_source["text"], label_candidates)
        if quote_span is not None:
            return page_source, quote_span
    return None, None


def _source_label_from_item(raw_item: dict[str, Any]) -> str | None:
    source_label = _clean_string(raw_item.get("source_label"))
    if source_label is not None:
        return source_label
    raw_evidence = raw_item.get("source_evidence", [])
    if isinstance(raw_evidence, list) and raw_evidence and isinstance(raw_evidence[0], dict):
        return _clean_string(raw_evidence[0].get("source_label"))
    return None


def _find_first_label_span(source_text: str, label_candidates: list[str]) -> tuple[int, int] | None:
    for candidate in label_candidates:
        cleaned = _clean_string(candidate)
        if cleaned is None:
            continue
        span = _find_label_span(source_text, cleaned)
        if span is not None:
            return span
    return None


def _label_lookup_candidates(display_label: str, mentioned_forms: list[str]) -> list[str]:
    candidates: list[str] = []
    for value in [display_label, *mentioned_forms]:
        cleaned = _clean_string(value)
        if cleaned is None:
            continue
        candidates.append(cleaned)

    parts = display_label.split()
    if len(parts) == 2 and parts[0][:1].isupper() and parts[1][:1].isupper():
        candidates.append(parts[1])

    seen: set[str] = set()
    unique_candidates: list[str] = []
    for candidate in candidates:
        key = _normalize_identity_key(candidate)
        if key and key not in seen:
            seen.add(key)
            unique_candidates.append(candidate)
    return unique_candidates


def _find_label_span(source_text: str, label_text: str) -> tuple[int, int] | None:
    label_start = source_text.find(label_text)
    if label_start >= 0:
        return label_start, label_start + len(label_text)

    normalized_source, source_index_map = _normalize_for_quote_lookup(source_text)
    normalized_label, _label_index_map = _normalize_for_quote_lookup(label_text)
    if len(normalized_label) < 3:
        return None
    normalized_start = normalized_source.casefold().find(normalized_label.casefold())
    if normalized_start < 0:
        return None
    normalized_end = normalized_start + len(normalized_label) - 1
    return source_index_map[normalized_start], source_index_map[normalized_end] + 1


def _normalize_for_quote_lookup(value: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    index_map: list[int] = []
    for index, char in enumerate(value):
        if char.isspace():
            continue
        chars.append(char)
        index_map.append(index)
    return "".join(chars), index_map


def _dedupe_key_for_item(item_kind: str, display_label: str, raw_item: dict[str, Any]) -> tuple[str, str]:
    mentioned_forms = _string_list(raw_item.get("mentioned_forms", []))
    candidates = [display_label, *mentioned_forms]
    normalized_candidates = [_normalize_identity_key(candidate) for candidate in candidates]
    useful_candidates = [candidate for candidate in normalized_candidates if candidate]
    return item_kind, min(useful_candidates) if useful_candidates else _normalize_identity_key(display_label)


def _repeated_item_keys(items: list[DocumentProcessingItemModel]) -> set[tuple[str, str]]:
    counts: dict[tuple[str, str], int] = {}
    for item in items:
        key = _dedupe_key_for_item(item.item_kind, item.display_label, {})
        counts[key] = counts.get(key, 0) + 1
    return {key for key, count in counts.items() if count > 1}


def _search_focus_from_item(raw_item: dict[str, Any], display_label: str) -> str:
    llm_focus = _clean_string(raw_item.get("recommended_search_focus"))
    if llm_focus is not None:
        return _compact_search_focus(display_label, _strip_terminal_period(llm_focus))
    return display_label


def _compact_search_focus(display_label: str, focus: str) -> str:
    stripped_focus = focus.strip()
    if not stripped_focus:
        return display_label
    if stripped_focus.startswith(display_label):
        tail = stripped_focus[len(display_label) :].strip()
        separator = re.match(r"^[,;:–-]\s*", tail)
        if separator is not None:
            tail = tail[separator.end() :]
        compact_tail = _first_focus_clause(tail)
        return f"{display_label} {compact_tail}".strip() if compact_tail else display_label
    return _first_focus_clause(stripped_focus) or display_label


def _first_focus_clause(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    first_clause = re.split(r"\s*[,;.!?]\s+", stripped, maxsplit=1)[0]
    first_clause = re.sub(r"\s+", " ", first_clause).strip()
    words = first_clause.split()
    if len(words) > 8:
        first_clause = " ".join(words[:8])
    return first_clause


def _strip_terminal_period(value: str) -> str:
    return re.sub(r"\s*\.\s*$", "", value).strip()


def _normalize_identity_key(value: str) -> str:
    cleaned = re.sub(r"\s*\([^)]*említés[^)]*\)\s*$", "", value, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", "", cleaned.casefold())
    cleaned = cleaned.replace(".", "").replace(",", "").replace(":", "").replace(";", "")
    return cleaned


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    strings: list[str] = []
    for item in value:
        cleaned = _clean_string(item)
        if cleaned is not None:
            strings.append(cleaned)
    return strings


def _object_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
