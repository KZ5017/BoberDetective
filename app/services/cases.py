import shutil
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analysis import AnalysisRunInputModel, AnalysisRunModel, AnalysisRunOutputModel
from app.models.audit import AuditEventModel
from app.models.case import CaseModel, CaseUserModel
from app.models.claim import ClaimModel, ClaimSourceModel
from app.models.contradiction import ContradictionCandidateModel, ContradictionCandidateSourceModel
from app.models.detached_source import DetachedSourceItemModel
from app.models.document import (
    DocumentChunkManifestModel,
    DocumentChunkModel,
    DocumentModel,
    DocumentPageModel,
    DocumentSearchEntryModel,
    DocumentTextLayerModel,
)
from app.models.document_processing import DocumentProcessingItemModel, FullDocumentAnswerModel
from app.models.entity import EntityMentionModel, EntityModel
from app.models.event import EventModel, EventSourceModel
from app.models.export import ExportItemModel, ExportModel
from app.models.missing_item import MissingItemCandidateModel, MissingItemCandidateSourceModel
from app.models.research_finding import ResearchFindingModel
from app.models.review import HumanReviewModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.case import CaseCreate
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.storage import StoragePaths
from app.services.users import get_or_create_dev_user
from app.services.vector_index import QdrantChunkIndex, VectorIndexError, chunk_collection_name


class CaseNotFoundError(ValueError):
    pass


class CaseDeletionError(RuntimeError):
    pass


def create_case(db: Session, payload: CaseCreate) -> CaseModel:
    user = get_or_create_dev_user(db)
    case = CaseModel(
        case_name=payload.case_name,
        case_reference=payload.case_reference,
        description=payload.description,
        status="open",
        created_by_user_id=user.id,
    )
    db.add(case)
    db.flush()

    membership = CaseUserModel(
        case_id=case.id,
        user_id=user.id,
        case_role="owner",
        granted_by_user_id=user.id,
    )
    db.add(membership)

    event = AuditEvent(
        event_type="case_created",
        success=True,
        case_id=str(case.id),
        user_id=str(user.id),
        related_object_type="case",
        related_object_id=str(case.id),
        input_summary={"case_reference": payload.case_reference},
        output_summary={"case_id": str(case.id), "case_name": case.case_name},
    )
    DatabaseAuditWriter(db).write(event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(event)
    db.commit()
    db.refresh(case)
    return case


def list_cases(db: Session) -> list[CaseModel]:
    return list(db.execute(select(CaseModel).order_by(CaseModel.created_at.desc())).scalars())


def delete_case_permanently(db: Session, case_id: UUID) -> dict:
    case = db.get(CaseModel, case_id)
    if case is None:
        raise CaseNotFoundError("Case not found")

    settings = get_settings()
    storage = StoragePaths(settings.data_root)
    user = get_or_create_dev_user(db)
    case_snapshot = {
        "case_id": str(case.id),
        "case_name": case.case_name,
        "case_reference": case.case_reference,
        "status": case.status,
    }
    counts = _case_delete_counts(db, case_id)
    vector_collection = chunk_collection_name(settings)

    try:
        QdrantChunkIndex(settings).delete_case_points(case_id)
    except VectorIndexError as exc:
        raise CaseDeletionError(f"Could not delete case vector index points: {exc}") from exc

    _delete_case_database_rows(db, case_id)

    audit_event = AuditEvent(
        event_type="case_deleted",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="case",
        related_object_id=str(case_id),
        input_summary=case_snapshot,
        output_summary={
            "deleted_counts": counts,
            "qdrant_collection": vector_collection,
            "qdrant_case_points_delete_requested": True,
            "case_storage_path": str(storage.case_dir(str(case_id))),
        },
    )
    DatabaseAuditWriter(db).write(audit_event)
    db.commit()
    JsonlAuditWriter(storage).write_global(audit_event)

    shutil.rmtree(storage.case_dir(str(case_id)), ignore_errors=True)
    return {
        "case_id": str(case_id),
        "deleted_counts": counts,
        "qdrant_collection": vector_collection,
    }


def _case_delete_counts(db: Session, case_id: UUID) -> dict[str, int]:
    return {
        "documents": _count_case_rows(db, DocumentModel, case_id),
        "document_pages": _count_case_rows(db, DocumentPageModel, case_id),
        "document_chunks": _count_case_rows(db, DocumentChunkModel, case_id),
        "source_references": _count_case_rows(db, SourceReferenceModel, case_id),
        "analysis_runs": _count_case_rows(db, AnalysisRunModel, case_id),
        "research_findings": _count_case_rows(db, ResearchFindingModel, case_id),
        "full_document_answers": _count_case_rows(db, FullDocumentAnswerModel, case_id),
        "claims": _count_case_rows(db, ClaimModel, case_id),
        "events": _count_case_rows(db, EventModel, case_id),
        "entities": _count_case_rows(db, EntityModel, case_id),
        "contradiction_candidates": _count_case_rows(db, ContradictionCandidateModel, case_id),
        "missing_item_candidates": _count_case_rows(db, MissingItemCandidateModel, case_id),
        "detached_source_items": _count_case_rows(db, DetachedSourceItemModel, case_id),
        "human_reviews": _count_case_rows(db, HumanReviewModel, case_id),
        "exports": _count_case_rows(db, ExportModel, case_id),
        "audit_events_preserved": _count_case_rows(db, AuditEventModel, case_id),
    }


def _count_case_rows(db: Session, model: type, case_id: UUID) -> int:
    return int(db.execute(select(func.count()).select_from(model).where(model.case_id == case_id)).scalar_one())


def _delete_case_database_rows(db: Session, case_id: UUID) -> None:
    run_ids = list(db.execute(select(AnalysisRunModel.id).where(AnalysisRunModel.case_id == case_id)).scalars())
    document_ids = list(db.execute(select(DocumentModel.id).where(DocumentModel.case_id == case_id)).scalars())
    page_ids = list(db.execute(select(DocumentPageModel.id).where(DocumentPageModel.case_id == case_id)).scalars())
    chunk_ids = list(db.execute(select(DocumentChunkModel.id).where(DocumentChunkModel.case_id == case_id)).scalars())
    source_reference_ids = list(db.execute(select(SourceReferenceModel.id).where(SourceReferenceModel.case_id == case_id)).scalars())
    claim_ids = list(db.execute(select(ClaimModel.id).where(ClaimModel.case_id == case_id)).scalars())
    event_ids = list(db.execute(select(EventModel.id).where(EventModel.case_id == case_id)).scalars())
    entity_ids = list(db.execute(select(EntityModel.id).where(EntityModel.case_id == case_id)).scalars())
    missing_item_ids = list(db.execute(select(MissingItemCandidateModel.id).where(MissingItemCandidateModel.case_id == case_id)).scalars())
    contradiction_ids = list(db.execute(select(ContradictionCandidateModel.id).where(ContradictionCandidateModel.case_id == case_id)).scalars())
    export_ids = list(db.execute(select(ExportModel.id).where(ExportModel.case_id == case_id)).scalars())

    if export_ids or source_reference_ids:
        conditions = []
        if export_ids:
            conditions.append(ExportItemModel.export_id.in_(export_ids))
        if source_reference_ids:
            conditions.append(ExportItemModel.source_reference_id.in_(source_reference_ids))
        db.execute(delete(ExportItemModel).where(or_(*conditions)))
    if run_ids:
        db.execute(delete(AnalysisRunOutputModel).where(AnalysisRunOutputModel.analysis_run_id.in_(run_ids)))
        db.execute(delete(AnalysisRunInputModel).where(AnalysisRunInputModel.analysis_run_id.in_(run_ids)))
    db.execute(delete(DocumentProcessingItemModel).where(DocumentProcessingItemModel.case_id == case_id))
    db.execute(delete(FullDocumentAnswerModel).where(FullDocumentAnswerModel.case_id == case_id))
    db.execute(delete(ResearchFindingModel).where(ResearchFindingModel.case_id == case_id))
    db.execute(delete(DetachedSourceItemModel).where(DetachedSourceItemModel.case_id == case_id))
    db.execute(delete(HumanReviewModel).where(HumanReviewModel.case_id == case_id))

    if contradiction_ids:
        db.execute(
            delete(ContradictionCandidateSourceModel).where(
                ContradictionCandidateSourceModel.contradiction_candidate_id.in_(contradiction_ids)
            )
        )
    db.execute(delete(ContradictionCandidateModel).where(ContradictionCandidateModel.case_id == case_id))

    if missing_item_ids:
        db.execute(
            delete(MissingItemCandidateSourceModel).where(
                MissingItemCandidateSourceModel.missing_item_candidate_id.in_(missing_item_ids)
            )
        )
    db.execute(delete(MissingItemCandidateModel).where(MissingItemCandidateModel.case_id == case_id))

    if event_ids:
        db.execute(delete(EventSourceModel).where(EventSourceModel.event_id.in_(event_ids)))
    db.execute(delete(EventModel).where(EventModel.case_id == case_id))

    if claim_ids:
        db.execute(delete(ClaimSourceModel).where(ClaimSourceModel.claim_id.in_(claim_ids)))
    db.execute(delete(ClaimModel).where(ClaimModel.case_id == case_id))

    if entity_ids:
        db.execute(delete(EntityMentionModel).where(EntityMentionModel.entity_id.in_(entity_ids)))
    db.execute(delete(EntityModel).where(EntityModel.case_id == case_id))

    db.execute(delete(SourceReferenceModel).where(SourceReferenceModel.case_id == case_id))
    db.execute(delete(ExportModel).where(ExportModel.case_id == case_id))

    db.execute(delete(DocumentSearchEntryModel).where(DocumentSearchEntryModel.case_id == case_id))
    db.execute(delete(DocumentChunkManifestModel).where(DocumentChunkManifestModel.case_id == case_id))
    db.execute(delete(DocumentTextLayerModel).where(DocumentTextLayerModel.case_id == case_id))
    db.execute(delete(DocumentChunkModel).where(DocumentChunkModel.case_id == case_id))
    db.execute(delete(DocumentPageModel).where(DocumentPageModel.case_id == case_id))

    if run_ids:
        db.execute(delete(AnalysisRunModel).where(AnalysisRunModel.id.in_(run_ids)))
    if document_ids:
        db.execute(delete(DocumentModel).where(DocumentModel.id.in_(document_ids)))
    db.execute(delete(CaseUserModel).where(CaseUserModel.case_id == case_id))
    db.execute(delete(CaseModel).where(CaseModel.id == case_id))
