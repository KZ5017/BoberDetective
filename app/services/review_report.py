from collections import Counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.claim import ClaimModel, ClaimSourceModel
from app.models.document import DocumentChunkModel, DocumentModel, DocumentPageModel
from app.models.entity import EntityMentionModel, EntityModel
from app.models.event import EventModel, EventSourceModel
from app.models.review import HumanReviewModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.review import HumanReviewRead
from app.schemas.review_report import CaseReviewReport, ReviewReportCounts, ReviewReportFilters, ReviewReportItem, ReviewReportSource


ALLOWED_OBJECT_TYPES = {"claim", "entity", "event"}
ALLOWED_REVIEW_STATUSES = {"new", "needs_review", "verified", "rejected", "corrected"}
ALLOWED_SOURCE_VALIDATION_STATUSES = {"pending_source_validation", "source_valid", "source_invalid"}
SOURCE_EXCERPT_CONTEXT_CHARS = 160


class ReviewReportValidationError(ValueError):
    pass


def build_case_review_report(
    db: Session,
    case_id: UUID,
    filters: ReviewReportFilters | None = None,
) -> CaseReviewReport:
    items = _claim_items(db, case_id) + _entity_items(db, case_id) + _event_items(db, case_id)
    items = _filter_items(items, filters or ReviewReportFilters())
    items.sort(key=lambda item: (item.review_status != "needs_review", item.created_at), reverse=False)
    counts = _build_counts([item.review_status for item in items])
    return CaseReviewReport(case_id=case_id, counts=counts, items=items)


def _filter_items(items: list[ReviewReportItem], filters: ReviewReportFilters) -> list[ReviewReportItem]:
    object_types = _normalized_filter_values(filters.object_types, ALLOWED_OBJECT_TYPES, "object_type")
    review_statuses = _normalized_filter_values(filters.review_statuses, ALLOWED_REVIEW_STATUSES, "review_status")
    source_validation_statuses = _normalized_filter_values(
        filters.source_validation_statuses,
        ALLOWED_SOURCE_VALIDATION_STATUSES,
        "source_validation_status",
    )
    filtered = items
    if object_types is not None:
        filtered = [item for item in filtered if item.object_type in object_types]
    if review_statuses is not None:
        filtered = [item for item in filtered if item.review_status in review_statuses]
    if source_validation_statuses is not None:
        filtered = [item for item in filtered if item.source_validation_status in source_validation_statuses]
    return filtered


def _normalized_filter_values(values: list[str] | None, allowed_values: set[str], field_name: str) -> set[str] | None:
    if values is None:
        return None
    normalized = {value.strip() for value in values if value.strip()}
    invalid_values = normalized - allowed_values
    if invalid_values:
        raise ReviewReportValidationError(f"Unsupported {field_name} filter value")
    return normalized or None


def _claim_items(db: Session, case_id: UUID) -> list[ReviewReportItem]:
    claims = list(
        db.execute(select(ClaimModel).where(ClaimModel.case_id == case_id).order_by(ClaimModel.created_at.desc())).scalars()
    )
    return [
        ReviewReportItem(
            object_type="claim",
            object_id=claim.id,
            title=claim.claim_text,
            body_text=claim.claim_text,
            subtype=claim.claim_type,
            review_status=claim.review_status,
            source_validation_status=claim.source_validation_status,
            created_by_analysis_run_id=claim.created_by_analysis_run_id,
            created_at=claim.created_at,
            updated_at=claim.updated_at,
            sources=_claim_sources(db, claim.id),
            reviews=_reviews(db, case_id, "claim", claim.id),
        )
        for claim in claims
    ]


def _event_items(db: Session, case_id: UUID) -> list[ReviewReportItem]:
    events = list(
        db.execute(
            select(EventModel)
            .where(EventModel.case_id == case_id)
            .order_by(EventModel.event_time_start.asc().nullslast(), EventModel.created_at.desc())
        ).scalars()
    )
    return [
        ReviewReportItem(
            object_type="event",
            object_id=event.id,
            title=event.event_title,
            body_text=event.event_description,
            subtype=event.event_type,
            review_status=event.review_status,
            source_validation_status=event.source_validation_status,
            created_by_analysis_run_id=event.created_by_analysis_run_id,
            created_at=event.created_at,
            updated_at=event.updated_at,
            sources=_event_sources(db, event.id),
            reviews=_reviews(db, case_id, "event", event.id),
        )
        for event in events
    ]


def _entity_items(db: Session, case_id: UUID) -> list[ReviewReportItem]:
    entities = list(
        db.execute(
            select(EntityModel)
            .where(EntityModel.case_id == case_id)
            .order_by(EntityModel.entity_type.asc(), EntityModel.canonical_name.asc())
        ).scalars()
    )
    items: list[ReviewReportItem] = []
    for entity in entities:
        sources = _entity_sources(db, entity.id)
        items.append(
            ReviewReportItem(
                object_type="entity",
                object_id=entity.id,
                title=entity.canonical_name,
                body_text=entity.description,
                subtype=entity.entity_type,
                review_status=entity.review_status,
                source_validation_status="source_valid" if sources else "source_invalid",
                created_by_analysis_run_id=entity.created_by_analysis_run_id,
                created_at=entity.created_at,
                updated_at=entity.updated_at,
                sources=sources,
                reviews=_reviews(db, case_id, "entity", entity.id),
            )
        )
    return items


def _claim_sources(db: Session, claim_id: UUID) -> list[ReviewReportSource]:
    rows = db.execute(
        select(ClaimSourceModel, SourceReferenceModel)
        .join(SourceReferenceModel, SourceReferenceModel.id == ClaimSourceModel.source_reference_id)
        .where(ClaimSourceModel.claim_id == claim_id)
        .order_by(ClaimSourceModel.relevance_rank.asc())
    )
    return [_report_source(db, source_link, source_reference) for source_link, source_reference in rows]


def _event_sources(db: Session, event_id: UUID) -> list[ReviewReportSource]:
    rows = db.execute(
        select(EventSourceModel, SourceReferenceModel)
        .join(SourceReferenceModel, SourceReferenceModel.id == EventSourceModel.source_reference_id)
        .where(EventSourceModel.event_id == event_id)
        .order_by(EventSourceModel.relevance_rank.asc())
    )
    return [_report_source(db, source_link, source_reference) for source_link, source_reference in rows]


def _entity_sources(db: Session, entity_id: UUID) -> list[ReviewReportSource]:
    rows = db.execute(
        select(EntityMentionModel, SourceReferenceModel)
        .join(SourceReferenceModel, SourceReferenceModel.id == EntityMentionModel.source_reference_id)
        .where(EntityMentionModel.entity_id == entity_id)
        .order_by(EntityMentionModel.created_at.asc())
    )
    return [
        _report_source_from_reference(
            db,
            source_reference,
            support_type="direct",
            relevance_rank=index,
        )
        for index, (_mention, source_reference) in enumerate(rows)
    ]


def _report_source(
    db: Session,
    source_link: ClaimSourceModel | EventSourceModel,
    source_reference: SourceReferenceModel,
) -> ReviewReportSource:
    return _report_source_from_reference(
        db,
        source_reference,
        support_type=source_link.support_type,
        relevance_rank=source_link.relevance_rank,
    )


def _report_source_from_reference(
    db: Session | None,
    source_reference: SourceReferenceModel,
    *,
    support_type: str,
    relevance_rank: int | None,
) -> ReviewReportSource:
    document = db.get(DocumentModel, source_reference.document_id) if db is not None else None
    page = db.get(DocumentPageModel, source_reference.page_id) if db is not None and source_reference.page_id else None
    chunk = db.get(DocumentChunkModel, source_reference.chunk_id) if db is not None and source_reference.chunk_id else None
    source_text = _source_text_for_excerpt(source_reference, page, chunk)
    excerpt, excerpt_start, excerpt_end = _source_excerpt(
        source_text,
        source_reference.quote_text,
        source_reference.quote_char_start,
        source_reference.quote_char_end,
    )
    return ReviewReportSource(
        source_reference_id=source_reference.id,
        document_id=source_reference.document_id,
        document_filename=document.original_filename if document is not None else None,
        document_sha256_hash=document.sha256_hash if document is not None else None,
        page_id=source_reference.page_id,
        chunk_id=source_reference.chunk_id,
        page_number=source_reference.page_number,
        chunk_index=chunk.chunk_index if chunk is not None else None,
        chunk_char_start=chunk.char_start if chunk is not None else None,
        chunk_char_end=chunk.char_end if chunk is not None else None,
        page_text_source=page.text_source if page is not None else None,
        page_ocr_used=page.ocr_used if page is not None else None,
        citation_label=source_reference.citation_label,
        quote_text=source_reference.quote_text,
        quote_char_start=source_reference.quote_char_start,
        quote_char_end=source_reference.quote_char_end,
        source_text_excerpt=excerpt,
        source_text_excerpt_char_start=excerpt_start,
        source_text_excerpt_char_end=excerpt_end,
        source_kind=source_reference.source_kind,
        support_type=support_type,
        relevance_rank=relevance_rank,
    )


def _source_text_for_excerpt(
    source_reference: SourceReferenceModel,
    page: DocumentPageModel | None,
    chunk: DocumentChunkModel | None,
) -> str | None:
    if source_reference.chunk_id is not None and chunk is not None:
        return chunk.chunk_text
    if source_reference.page_id is not None and page is not None:
        return page.extracted_text
    return None


def _source_excerpt(
    source_text: str | None,
    quote_text: str,
    quote_char_start: int | None,
    quote_char_end: int | None,
) -> tuple[str | None, int | None, int | None]:
    if source_text is None:
        return None, None, None
    quote_start = quote_char_start
    quote_end = quote_char_end
    if quote_start is None or quote_end is None or source_text[quote_start:quote_end] != quote_text:
        found_at = source_text.find(quote_text)
        if found_at < 0:
            return None, None, None
        quote_start = found_at
        quote_end = found_at + len(quote_text)
    excerpt_start = max(0, quote_start - SOURCE_EXCERPT_CONTEXT_CHARS)
    excerpt_end = min(len(source_text), quote_end + SOURCE_EXCERPT_CONTEXT_CHARS)
    return source_text[excerpt_start:excerpt_end], excerpt_start, excerpt_end


def _reviews(db: Session, case_id: UUID, object_type: str, object_id: UUID) -> list[HumanReviewRead]:
    reviews = db.execute(
        select(HumanReviewModel)
        .where(
            HumanReviewModel.case_id == case_id,
            HumanReviewModel.object_type == object_type,
            HumanReviewModel.object_id == object_id,
        )
        .order_by(HumanReviewModel.performed_at.desc())
    ).scalars()
    return [HumanReviewRead.model_validate(review) for review in reviews]


def _build_counts(review_statuses: list[str]) -> ReviewReportCounts:
    counter = Counter(review_statuses)
    return ReviewReportCounts(
        total=len(review_statuses),
        needs_review=counter["needs_review"],
        verified=counter["verified"],
        rejected=counter["rejected"],
        corrected=counter["corrected"],
        new=counter["new"],
    )
