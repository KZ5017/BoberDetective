from dataclasses import dataclass
from datetime import UTC, datetime
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import DocumentModel, DocumentPageModel
from app.models.document_processing import DocumentProcessingItemModel
from app.schemas.full_document_processing import (
    DocumentProcessingItemRead,
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
        key="entity_search_seeds",
        label="Entitáskeresési fókuszok",
        description="Teljes iratból kinyert szervezetek, helyek, hivatkozások, mellékletek és egyéb fókuszok előállítása.",
        item_kinds=("organization", "location", "document_reference", "case_reference", "attachment", "other"),
    ),
)

PROFILE_KEYS = {profile.key for profile in PROFILES}
WORK_STATUSES = {"active", "set_aside", "converted", "deleted"}
USER_SETTABLE_WORK_STATUSES = {"active", "set_aside", "deleted"}
FULL_DOCUMENT_PROCESSING_SYSTEM_PROMPT = """You are a source-faithful investigative document processing component.
You work with Hungarian source documents.
The source document is the only source of truth.
Do not use outside knowledge.
Do not infer guilt, responsibility, legal qualification, risk, or personal blame.
Return only a valid JSON object.
Every item must be supported by at least one source_evidence entry.
Each source_evidence.quote_text must be copied character-exactly from the matching SOURCE page.
Write display_label, short_description, recommended_search_focus, alternative_search_focuses, source_supported_details, relationships, and unsupported_items in Hungarian.
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
                max_tokens=None,
            )
            parsed = parse_llm_json_object(completion.content)
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
            items=[DocumentProcessingItemRead.model_validate(item) for item in created_items],
            unsupported_items=unsupported_items,
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
    allowed_kinds = ", ".join(profile.item_kinds)
    return f"""DOCUMENT:
{document.original_filename}

PROFILE:
{profile.key} - {profile.description}

SOURCE:
{source_pages}

TASK:
Goal:
- Extract source-backed full-document processing items for the selected profile.
- The SOURCE contains the selected Hungarian pages from one document.
- Allowed item_kind values for this profile: {allowed_kinds}.
- If this profile is for persons, extract concrete persons and useful person-focused search seeds.
- If this profile is for entities, extract concrete organizations, locations, document references, case references, attachments, or other useful search seeds.

Selection rules:
- Return an item only when the SOURCE directly names or clearly identifies the item.
- Each item must help a later human start a focused keyword, semantic, or hybrid search.
- Do not repeat the same display_label or the same person/entity as multiple JSON items.
- Do not create numbered mention items such as "(second mention)" or "(third mention)".
- Do not create a general document summary.
- Do not merge unrelated people or entities.
- Do not invent missing names, roles, relationships, or details.

Field rules:
- display_label must be a short Hungarian label for the item.
- short_description must contain only source-supported information.
- recommended_search_focus should combine the label with a useful source-supported role, attribute, relation, location, or reference when available.
- alternative_search_focuses may include short Hungarian variants useful for later search.
- source_supported_details must be an array of objects with source-supported details.
- relationships must be an array of objects only when the source directly supports the relationship.
- source_evidence must contain at least one object with source_label and quote_text.
- Use only 1-2 source_evidence entries per item unless more are essential.
- quote_text must be copied character-exactly from the matching SOURCE page.
- Do not use ellipses, shortened quotes, repaired OCR text, or normalized spacing in quote_text.

Unsupported items:
- If something looks interesting but lacks direct source evidence, put a short Hungarian reason into unsupported_items.

Expected JSON shape:
{{
  "items": [
    {{
      "item_kind": "{profile.item_kinds[0]}",
      "display_label": "...",
      "short_description": "...",
      "mentioned_forms": ["..."],
      "source_supported_details": [{{"detail": "...", "source_label": "page_1"}}],
      "relationships": [{{"relation": "...", "target": "...", "source_label": "page_1"}}],
      "recommended_search_focus": "...",
      "alternative_search_focuses": ["..."],
      "source_evidence": [{{"source_label": "page_1", "quote_text": "..."}}]
    }}
  ],
  "unsupported_items": ["..."]
}}"""


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
    seen_item_keys: set[tuple[str, str]] = set()
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
        item_key = _dedupe_key_for_item(item_kind, display_label, raw_item)

        raw_evidence = raw_item.get("source_evidence", [])
        if not isinstance(raw_evidence, list) or not raw_evidence:
            unsupported_items.append(f"{display_label}: hiányzó forrásbizonyíték")
            continue
        valid_evidence: list[dict[str, Any]] = []
        invalid_evidence = False
        for evidence_index, evidence in enumerate(raw_evidence, start=1):
            if not isinstance(evidence, dict):
                invalid_evidence = True
                unsupported_items.append(f"{display_label}: hibás forrásbizonyíték #{evidence_index}")
                break
            source_label = _clean_string(evidence.get("source_label"))
            quote_text = _clean_string(evidence.get("quote_text"))
            page_source = page_by_label.get(source_label or "")
            if page_source is None or quote_text is None:
                invalid_evidence = True
                unsupported_items.append(f"{display_label}: hiányzó vagy ismeretlen forráscímke")
                break
            quote_span = _find_quote_span(page_source["text"], quote_text)
            if quote_span is None:
                invalid_evidence = True
                unsupported_items.append(f"{display_label}: az idézet nem található karakterpontosan a forrásoldalon")
                break
            quote_start, quote_end = quote_span
            exact_quote_text = page_source["text"][quote_start:quote_end]
            valid_evidence.append(
                {
                    "source_label": source_label,
                    "quote_text": exact_quote_text,
                    "document_id": str(page_source["document_id"]),
                    "page_id": str(page_source["page_id"]),
                    "page_number": page_source["page_number"],
                    "quote_char_start": quote_start,
                    "quote_char_end": quote_end,
                }
            )
        if invalid_evidence or not valid_evidence:
            continue
        if item_key in seen_item_keys:
            unsupported_items.append(f"{display_label}: ismétlődő elem")
            continue
        seen_item_keys.add(item_key)

        valid_items.append(
            {
                "item_kind": item_kind,
                "display_label": display_label,
                "short_description": _clean_string(raw_item.get("short_description")),
                "mentioned_forms": _string_list(raw_item.get("mentioned_forms", [])),
                "source_supported_details": _object_list(raw_item.get("source_supported_details", [])),
                "relationships": _object_list(raw_item.get("relationships", [])),
                "recommended_search_focus": _clean_string(raw_item.get("recommended_search_focus")) or display_label,
                "alternative_search_focuses": _string_list(raw_item.get("alternative_search_focuses", [])),
                "source_evidence": valid_evidence,
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
