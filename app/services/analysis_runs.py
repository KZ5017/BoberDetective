from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analysis import AnalysisRunInputModel, AnalysisRunModel, AnalysisRunOutputModel
from app.models.case import CaseModel
from app.models.claim import ClaimModel, ClaimSourceModel
from app.models.contradiction import ContradictionCandidateModel, ContradictionCandidateSourceModel
from app.models.document import DocumentChunkModel, DocumentModel
from app.models.document_processing import DocumentProcessingItemModel
from app.models.entity import EntityMentionModel, EntityModel
from app.models.event import EventModel, EventSourceModel
from app.models.missing_item import MissingItemCandidateModel, MissingItemCandidateSourceModel
from app.models.research_finding import ResearchFindingModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.analysis import AnalysisRunOutputSummary, AnalysisRunSourceSummary
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.storage import StoragePaths
from app.services.text_store import read_chunk_text_from_store
from app.services.users import get_or_create_dev_user


class AnalysisRunError(ValueError):
    pass


class AnalysisRunNotFoundError(AnalysisRunError):
    pass


class AnalysisRunValidationError(AnalysisRunError):
    pass


def list_analysis_runs(db: Session, case_id: UUID) -> list[AnalysisRunModel]:
    return list(
        db.execute(
            select(AnalysisRunModel)
            .where(AnalysisRunModel.case_id == case_id)
            .order_by(AnalysisRunModel.started_at.desc())
        ).scalars()
    )


def get_analysis_run(db: Session, case_id: UUID, analysis_run_id: UUID) -> AnalysisRunModel:
    run = db.get(AnalysisRunModel, analysis_run_id)
    if run is None or run.case_id != case_id:
        raise AnalysisRunNotFoundError("Analysis run not found")
    return run


def list_analysis_run_inputs(db: Session, analysis_run_id: UUID) -> list[AnalysisRunInputModel]:
    return list(
        db.execute(
            select(AnalysisRunInputModel)
            .where(AnalysisRunInputModel.analysis_run_id == analysis_run_id)
            .order_by(AnalysisRunInputModel.sequence_no.asc())
        ).scalars()
    )


def list_analysis_run_outputs(db: Session, analysis_run_id: UUID) -> list[AnalysisRunOutputModel]:
    return list(
        db.execute(
            select(AnalysisRunOutputModel)
            .where(AnalysisRunOutputModel.analysis_run_id == analysis_run_id)
            .order_by(AnalysisRunOutputModel.output_position.asc().nulls_last())
        ).scalars()
    )


def analysis_input_source_summary(db: Session, item: AnalysisRunInputModel) -> AnalysisRunSourceSummary | None:
    chunk = item.chunk if item.chunk_id is not None else None
    document = item.document if item.document_id is not None else None
    if chunk is not None and document is None:
        document = db.get(DocumentModel, chunk.document_id)
    if chunk is None and document is None:
        return None
    return AnalysisRunSourceSummary(
        document_filename=document.original_filename if document is not None else None,
        page_start=chunk.page_start if chunk is not None else None,
        page_end=chunk.page_end if chunk is not None else None,
        chunk_index=chunk.chunk_index if chunk is not None else None,
        char_start=chunk.char_start if chunk is not None else None,
        char_end=chunk.char_end if chunk is not None else None,
        text_preview=_bounded_preview(read_chunk_text_from_store(db, chunk)) if chunk is not None else None,
    )


def analysis_output_summary(db: Session, item: AnalysisRunOutputModel) -> AnalysisRunOutputSummary | None:
    if item.output_type == "claim":
        claim = db.get(ClaimModel, item.output_object_id)
        if claim is None:
            return None
        return AnalysisRunOutputSummary(
            title=claim.claim_title,
            body_text=claim.claim_text,
            review_status=claim.review_status,
            source_validation_status=claim.source_validation_status,
            source_count=_count_sources(db, ClaimSourceModel.claim_id, claim.id),
        )
    if item.output_type == "event":
        event = db.get(EventModel, item.output_object_id)
        if event is None:
            return None
        return AnalysisRunOutputSummary(
            title=event.event_title,
            body_text=event.event_description,
            review_status=event.review_status,
            source_validation_status=event.source_validation_status,
            source_count=_count_sources(db, EventSourceModel.event_id, event.id),
        )
    if item.output_type == "entity":
        entity = db.get(EntityModel, item.output_object_id)
        if entity is None:
            return None
        return AnalysisRunOutputSummary(
            title=entity.canonical_name,
            body_text=entity.description,
            review_status=entity.review_status,
            source_count=_count_sources(db, EntityMentionModel.entity_id, entity.id),
        )
    if item.output_type == "missing_item_candidate":
        candidate = db.get(MissingItemCandidateModel, item.output_object_id)
        if candidate is None:
            return None
        return AnalysisRunOutputSummary(
            title=candidate.referenced_item_text,
            body_text=candidate.description,
            review_status=candidate.review_status,
            source_validation_status=candidate.source_validation_status,
            source_count=_count_sources(db, MissingItemCandidateSourceModel.missing_item_candidate_id, candidate.id),
        )
    if item.output_type == "contradiction_candidate":
        candidate = db.get(ContradictionCandidateModel, item.output_object_id)
        if candidate is None:
            return None
        return AnalysisRunOutputSummary(
            title=candidate.title,
            body_text=candidate.description,
            review_status=candidate.review_status,
            source_validation_status=candidate.source_validation_status,
            source_count=_count_sources(db, ContradictionCandidateSourceModel.contradiction_candidate_id, candidate.id),
        )
    if item.output_type == "research_finding":
        finding = db.get(ResearchFindingModel, item.output_object_id)
        if finding is None:
            return None
        return AnalysisRunOutputSummary(
            title=finding.title,
            body_text=finding.finding_text,
            source_validation_status=finding.source_validation_status,
            source_count=1,
        )
    if item.output_type == "document_processing_item":
        processing_item = db.get(DocumentProcessingItemModel, item.output_object_id)
        if processing_item is None:
            return None
        return AnalysisRunOutputSummary(
            title=processing_item.display_label,
            body_text=processing_item.short_description,
            source_count=len(processing_item.source_evidence_json or []),
        )
    if item.output_type == "source_reference":
        source = db.get(SourceReferenceModel, item.output_object_id)
        if source is None:
            return None
        document = db.get(DocumentModel, source.document_id)
        return AnalysisRunOutputSummary(
            title=document.original_filename if document is not None else "Forrashivatkozas",
            body_text=_bounded_preview(source.quote_text),
        )
    if item.output_type == "chunk":
        chunk = db.get(DocumentChunkModel, item.output_object_id)
        if chunk is None:
            return None
        document = db.get(DocumentModel, chunk.document_id)
        return AnalysisRunOutputSummary(
            title=document.original_filename if document is not None else "Szovegresz",
            body_text=_bounded_preview(read_chunk_text_from_store(db, chunk)),
        )
    return None


def _count_sources(db: Session, column, object_id: UUID) -> int:
    return int(db.execute(select(func.count()).where(column == object_id)).scalar_one())


def _bounded_preview(text: str | None, limit: int = 360) -> str | None:
    if text is None:
        return None
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."


def start_analysis_run(
    db: Session,
    case_id: UUID,
    run_type: str,
    *,
    provider_type: str | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
    input_parameters: dict | None = None,
    prompt_template_name: str | None = None,
    prompt_template_version: str | None = None,
    output_schema_name: str | None = None,
    output_schema_version: str | None = None,
    retrieval_strategy: str | None = None,
    raw_prompt_text: str | None = None,
) -> AnalysisRunModel:
    if db.get(CaseModel, case_id) is None:
        raise AnalysisRunValidationError("Case not found")
    user = get_or_create_dev_user(db)
    run = AnalysisRunModel(
        case_id=case_id,
        run_type=run_type,
        status="running",
        started_by_user_id=user.id,
        provider_type=provider_type,
        model_name=model_name,
        model_version=model_version,
        input_parameters=input_parameters,
        prompt_template_name=prompt_template_name,
        prompt_template_version=prompt_template_version,
        output_schema_name=output_schema_name,
        output_schema_version=output_schema_version,
        retrieval_strategy=retrieval_strategy,
        raw_prompt_text=raw_prompt_text,
    )
    db.add(run)
    db.flush()
    _write_run_audit(db, run, "analysis_run_started", True, {"run_type": run_type}, {})
    db.commit()
    db.refresh(run)
    return run


def add_analysis_run_input(
    db: Session,
    analysis_run_id: UUID,
    input_type: str,
    sequence_no: int,
    *,
    document_id: UUID | None = None,
    page_id: UUID | None = None,
    chunk_id: UUID | None = None,
    related_object_type: str | None = None,
    related_object_id: UUID | None = None,
    payload_json: dict | None = None,
) -> AnalysisRunInputModel:
    item = AnalysisRunInputModel(
        analysis_run_id=analysis_run_id,
        input_type=input_type,
        document_id=document_id,
        page_id=page_id,
        chunk_id=chunk_id,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        sequence_no=sequence_no,
        payload_json=payload_json,
    )
    db.add(item)
    db.flush()
    return item


def add_analysis_run_output(
    db: Session,
    analysis_run_id: UUID,
    output_type: str,
    output_object_id: UUID,
    output_position: int | None = None,
) -> AnalysisRunOutputModel:
    item = AnalysisRunOutputModel(
        analysis_run_id=analysis_run_id,
        output_type=output_type,
        output_object_id=output_object_id,
        output_position=output_position,
    )
    db.add(item)
    db.flush()
    return item


def finish_analysis_run(
    db: Session,
    run: AnalysisRunModel,
    *,
    status: str,
    validation_status: str | None = None,
    error_message: str | None = None,
    output_summary: dict | None = None,
) -> AnalysisRunModel:
    if status not in {"succeeded", "failed", "cancelled"}:
        raise AnalysisRunValidationError("Analysis run finish status must be terminal")
    run.status = status
    run.finished_at = datetime.now(UTC)
    run.validation_status = validation_status
    run.error_message = error_message
    db.add(run)
    db.flush()
    _write_run_audit(
        db,
        run,
        f"analysis_run_{status}",
        status == "succeeded",
        {"run_type": run.run_type},
        output_summary or {},
        error_message=error_message,
    )
    db.commit()
    db.refresh(run)
    return run


def _write_run_audit(
    db: Session,
    run: AnalysisRunModel,
    event_type: str,
    success: bool,
    input_summary: dict,
    output_summary: dict,
    error_message: str | None = None,
) -> None:
    event = AuditEvent(
        event_type=event_type,
        success=success,
        case_id=str(run.case_id),
        user_id=str(run.started_by_user_id),
        analysis_run_id=str(run.id),
        related_object_type="analysis_run",
        related_object_id=str(run.id),
        input_summary=input_summary,
        output_summary=output_summary,
        error_message=error_message,
    )
    DatabaseAuditWriter(db).write(event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(event)
