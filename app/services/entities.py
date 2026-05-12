from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analysis import AnalysisRunModel
from app.models.entity import EntityMentionModel, EntityModel
from app.models.source_reference import SourceReferenceModel
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.storage import StoragePaths


class EntityError(ValueError):
    pass


class EntityNotFoundError(EntityError):
    pass


class EntityValidationError(EntityError):
    pass


def list_entities(db: Session, case_id: UUID) -> list[EntityModel]:
    return list(
        db.execute(
            select(EntityModel)
            .where(EntityModel.case_id == case_id)
            .order_by(EntityModel.entity_type.asc(), EntityModel.canonical_name.asc())
        ).scalars()
    )


def get_entity(db: Session, case_id: UUID, entity_id: UUID) -> EntityModel:
    entity = db.get(EntityModel, entity_id)
    if entity is None or entity.case_id != case_id:
        raise EntityNotFoundError("Entity not found")
    return entity


def list_entity_mentions(db: Session, entity_id: UUID) -> list[EntityMentionModel]:
    return list(
        db.execute(
            select(EntityMentionModel)
            .where(EntityMentionModel.entity_id == entity_id)
            .order_by(EntityMentionModel.created_at.asc())
        ).scalars()
    )


def create_entity_with_mention(
    db: Session,
    *,
    case_id: UUID,
    entity_type: str,
    canonical_name: str,
    normalized_value: str | None,
    description: str | None,
    surface_text: str,
    source_reference_id: UUID,
    analysis_run_id: UUID,
) -> tuple[EntityModel, EntityMentionModel]:
    if canonical_name.strip() == "":
        raise EntityValidationError("Entity canonical name is required")
    if surface_text.strip() == "":
        raise EntityValidationError("Entity mention surface text is required")

    run = db.get(AnalysisRunModel, analysis_run_id)
    if run is None or run.case_id != case_id:
        raise EntityValidationError("Analysis run not found for this case")

    source_reference = db.get(SourceReferenceModel, source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise EntityValidationError("Source reference not found for this case")

    entity = EntityModel(
        case_id=case_id,
        entity_type=entity_type,
        canonical_name=canonical_name,
        normalized_value=normalized_value,
        description=description,
        created_by_analysis_run_id=analysis_run_id,
        review_status="needs_review",
    )
    db.add(entity)
    db.flush()

    mention = EntityMentionModel(
        case_id=case_id,
        entity_id=entity.id,
        document_id=source_reference.document_id,
        page_id=source_reference.page_id,
        chunk_id=source_reference.chunk_id,
        page_number=source_reference.page_number,
        surface_text=surface_text,
        char_start=source_reference.quote_char_start,
        char_end=source_reference.quote_char_end,
        source_reference_id=source_reference.id,
        created_by_analysis_run_id=analysis_run_id,
    )
    db.add(mention)
    db.flush()

    audit_event = AuditEvent(
        event_type="entity_created",
        success=True,
        case_id=str(case_id),
        user_id=str(run.started_by_user_id),
        analysis_run_id=str(analysis_run_id),
        related_object_type="entity",
        related_object_id=str(entity.id),
        related_document_id=str(source_reference.document_id),
        related_page_id=str(source_reference.page_id) if source_reference.page_id is not None else None,
        related_chunk_id=str(source_reference.chunk_id) if source_reference.chunk_id is not None else None,
        input_summary={"source_reference_id": str(source_reference.id)},
        output_summary={"entity_id": str(entity.id), "entity_type": entity.entity_type},
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(entity)
    db.refresh(mention)
    return entity, mention
