from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.claim import ClaimModel, ClaimSourceModel
from app.models.contradiction import ContradictionCandidateModel
from app.models.entity import EntityMentionModel, EntityModel
from app.models.event import EventModel, EventSourceModel
from app.models.missing_item import MissingItemCandidateModel, MissingItemCandidateSourceModel
from app.models.source_reference import SourceReferenceModel


def normalize_for_dedup(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def find_duplicate_claim(
    db: Session,
    *,
    case_id: UUID,
    claim_type: str,
    claim_text: str,
    document_id: UUID,
    chunk_id: UUID | None,
    quote_text: str,
) -> tuple[ClaimModel, SourceReferenceModel] | None:
    rows = db.execute(
        select(ClaimModel, SourceReferenceModel)
        .join(ClaimSourceModel, ClaimSourceModel.claim_id == ClaimModel.id)
        .join(SourceReferenceModel, SourceReferenceModel.id == ClaimSourceModel.source_reference_id)
        .where(
            ClaimModel.case_id == case_id,
            ClaimModel.claim_type == claim_type,
        )
    ).all()
    return _first_matching_text(rows, claim_text, lambda row: row[0].claim_text)


def find_duplicate_event(
    db: Session,
    *,
    case_id: UUID,
    event_type: str,
    event_title: str,
    event_time_start: datetime | None,
    time_precision: str | None = None,
    document_id: UUID | None = None,
    chunk_id: UUID | None = None,
    quote_text: str | None = None,
) -> tuple[EventModel, SourceReferenceModel] | None:
    rows = db.execute(
        select(EventModel, SourceReferenceModel)
        .join(EventSourceModel, EventSourceModel.event_id == EventModel.id)
        .join(SourceReferenceModel, SourceReferenceModel.id == EventSourceModel.source_reference_id)
        .where(
            EventModel.case_id == case_id,
            EventModel.event_type == event_type,
        )
    ).all()
    expected_title = normalize_for_dedup(event_title)
    for event, source_reference in rows:
        if (
            normalize_for_dedup(event.event_title) == expected_title
            and event.event_time_start == event_time_start
            and normalize_for_dedup(event.time_precision) == normalize_for_dedup(time_precision)
        ):
            return event, source_reference
    return None


def find_duplicate_entity(
    db: Session,
    *,
    case_id: UUID,
    entity_type: str,
    canonical_name: str,
    surface_text: str,
    normalized_value: str | None = None,
    document_id: UUID | None = None,
    chunk_id: UUID | None = None,
    quote_text: str | None = None,
) -> tuple[EntityModel, EntityMentionModel, SourceReferenceModel] | None:
    rows = db.execute(
        select(EntityModel, EntityMentionModel, SourceReferenceModel)
        .join(EntityMentionModel, EntityMentionModel.entity_id == EntityModel.id)
        .join(SourceReferenceModel, SourceReferenceModel.id == EntityMentionModel.source_reference_id)
        .where(
            EntityModel.case_id == case_id,
            EntityModel.entity_type == entity_type,
        )
    ).all()
    expected_name = normalize_for_dedup(canonical_name)
    expected_normalized_value = normalize_for_dedup(normalized_value)
    for entity, mention, source_reference in rows:
        same_name = normalize_for_dedup(entity.canonical_name) == expected_name
        same_normalized_value = expected_normalized_value != "" and normalize_for_dedup(entity.normalized_value) == expected_normalized_value
        if same_name or same_normalized_value:
            return entity, mention, source_reference
    return None


def find_duplicate_missing_item_candidate(
    db: Session,
    *,
    case_id: UUID,
    missing_item_type: str,
    referenced_item_text: str,
    document_id: UUID | None = None,
    chunk_id: UUID | None = None,
    quote_text: str | None = None,
) -> tuple[MissingItemCandidateModel, SourceReferenceModel] | None:
    rows = db.execute(
        select(MissingItemCandidateModel, SourceReferenceModel)
        .join(
            MissingItemCandidateSourceModel,
            MissingItemCandidateSourceModel.missing_item_candidate_id == MissingItemCandidateModel.id,
        )
        .join(SourceReferenceModel, SourceReferenceModel.id == MissingItemCandidateSourceModel.source_reference_id)
        .where(
            MissingItemCandidateModel.case_id == case_id,
            MissingItemCandidateModel.missing_item_type == missing_item_type,
        )
    ).all()
    expected_text = normalize_for_dedup(referenced_item_text)
    for candidate, source_reference in rows:
        if normalize_for_dedup(candidate.referenced_item_text) == expected_text:
            return candidate, source_reference
    return None


def find_duplicate_contradiction_candidate(
    db: Session,
    *,
    case_id: UUID,
    contradiction_type: str,
    claim_id_a: UUID | None,
    claim_id_b: UUID | None,
    event_id_a: UUID | None = None,
    event_id_b: UUID | None = None,
) -> ContradictionCandidateModel | None:
    pair_filter = _pair_filter(
        ContradictionCandidateModel.claim_id_a,
        ContradictionCandidateModel.claim_id_b,
        claim_id_a,
        claim_id_b,
    )
    if pair_filter is None:
        pair_filter = _pair_filter(
            ContradictionCandidateModel.event_id_a,
            ContradictionCandidateModel.event_id_b,
            event_id_a,
            event_id_b,
        )
    if pair_filter is None:
        return None
    return db.execute(
        select(ContradictionCandidateModel)
        .where(
            ContradictionCandidateModel.case_id == case_id,
            ContradictionCandidateModel.contradiction_type == contradiction_type,
            pair_filter,
        )
        .order_by(ContradictionCandidateModel.created_at.desc())
    ).scalars().first()


def _first_matching_text(
    rows: Iterable[tuple],
    object_text: str,
    get_object_text,
):
    expected_object_text = normalize_for_dedup(object_text)
    for row in rows:
        source_reference = row[1]
        if normalize_for_dedup(get_object_text(row)) == expected_object_text:
            return row[0], source_reference
    return None


def _pair_filter(column_a, column_b, id_a: UUID | None, id_b: UUID | None):
    if id_a is None or id_b is None:
        return None
    return or_(
        and_(column_a == id_a, column_b == id_b),
        and_(column_a == id_b, column_b == id_a),
    )
