from collections import Counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.claim import ClaimModel, ClaimSourceModel
from app.models.event import EventModel, EventSourceModel
from app.models.review import HumanReviewModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.review import HumanReviewRead
from app.schemas.review_report import CaseReviewReport, ReviewReportCounts, ReviewReportItem, ReviewReportSource


def build_case_review_report(db: Session, case_id: UUID) -> CaseReviewReport:
    items = _claim_items(db, case_id) + _event_items(db, case_id)
    items.sort(key=lambda item: (item.review_status != "needs_review", item.created_at), reverse=False)
    counts = _build_counts([item.review_status for item in items])
    return CaseReviewReport(case_id=case_id, counts=counts, items=items)


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


def _claim_sources(db: Session, claim_id: UUID) -> list[ReviewReportSource]:
    rows = db.execute(
        select(ClaimSourceModel, SourceReferenceModel)
        .join(SourceReferenceModel, SourceReferenceModel.id == ClaimSourceModel.source_reference_id)
        .where(ClaimSourceModel.claim_id == claim_id)
        .order_by(ClaimSourceModel.relevance_rank.asc())
    )
    return [_report_source(source_link, source_reference) for source_link, source_reference in rows]


def _event_sources(db: Session, event_id: UUID) -> list[ReviewReportSource]:
    rows = db.execute(
        select(EventSourceModel, SourceReferenceModel)
        .join(SourceReferenceModel, SourceReferenceModel.id == EventSourceModel.source_reference_id)
        .where(EventSourceModel.event_id == event_id)
        .order_by(EventSourceModel.relevance_rank.asc())
    )
    return [_report_source(source_link, source_reference) for source_link, source_reference in rows]


def _report_source(source_link: ClaimSourceModel | EventSourceModel, source_reference: SourceReferenceModel) -> ReviewReportSource:
    return ReviewReportSource(
        source_reference_id=source_reference.id,
        document_id=source_reference.document_id,
        page_id=source_reference.page_id,
        chunk_id=source_reference.chunk_id,
        page_number=source_reference.page_number,
        citation_label=source_reference.citation_label,
        quote_text=source_reference.quote_text,
        source_kind=source_reference.source_kind,
        support_type=source_link.support_type,
        relevance_rank=source_link.relevance_rank,
    )


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
