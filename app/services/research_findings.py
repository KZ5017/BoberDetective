from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analysis import AnalysisRunModel
from app.models.research_finding import ResearchFindingModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.manual_entry import ManualObjectFromSourceCreate
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.manual_entries import ManualEntryError, create_manual_object_from_source_reference
from app.services.source_references import ensure_source_reference_document_is_active
from app.services.storage import StoragePaths


class ResearchFindingError(ValueError):
    pass


class ResearchFindingNotFoundError(ResearchFindingError):
    pass


class ResearchFindingValidationError(ResearchFindingError):
    pass


def list_research_findings(db: Session, case_id: UUID) -> list[ResearchFindingModel]:
    return list(
        db.execute(
            select(ResearchFindingModel)
            .where(
                ResearchFindingModel.case_id == case_id,
                ResearchFindingModel.conversion_status != "converted",
            )
            .order_by(ResearchFindingModel.created_at.desc())
        ).scalars()
    )


def get_research_finding(db: Session, case_id: UUID, finding_id: UUID) -> ResearchFindingModel:
    finding = db.get(ResearchFindingModel, finding_id)
    if finding is None or finding.case_id != case_id:
        raise ResearchFindingNotFoundError("Research finding not found")
    return finding


def create_research_finding(
    db: Session,
    *,
    case_id: UUID,
    title: str,
    finding_text: str,
    relevance_reason: str,
    source_reference_id: UUID,
    analysis_run_id: UUID,
    suggested_type: str = "other",
    suggested_type_reason: str | None = None,
    llm_support_status: str = "confirmed",
    source_validation_status: str = "source_valid",
) -> ResearchFindingModel:
    if title.strip() == "":
        raise ResearchFindingValidationError("Research finding title is required")
    if finding_text.strip() == "":
        raise ResearchFindingValidationError("Research finding text is required")
    if relevance_reason.strip() == "":
        raise ResearchFindingValidationError("Research finding relevance reason is required")
    if suggested_type not in {"claim", "event", "entity", "document_reference", "other"}:
        raise ResearchFindingValidationError("Unsupported research finding suggested type")
    if llm_support_status not in {"confirmed", "unconfirmed"}:
        raise ResearchFindingValidationError("Unsupported research finding LLM support status")
    if source_validation_status not in {"pending_source_validation", "source_valid", "source_invalid"}:
        raise ResearchFindingValidationError("Unsupported research finding source validation status")

    run = db.get(AnalysisRunModel, analysis_run_id)
    if run is None or run.case_id != case_id:
        raise ResearchFindingValidationError("Analysis run not found for this case")

    source_reference = db.get(SourceReferenceModel, source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise ResearchFindingValidationError("Source reference not found for this case")
    ensure_source_reference_document_is_active(db, case_id, source_reference, ResearchFindingValidationError)

    finding = ResearchFindingModel(
        case_id=case_id,
        analysis_run_id=analysis_run_id,
        source_reference_id=source_reference_id,
        title=title.strip(),
        finding_text=finding_text.strip(),
        suggested_type=suggested_type,
        suggested_type_reason=suggested_type_reason.strip() if isinstance(suggested_type_reason, str) and suggested_type_reason.strip() else None,
        relevance_reason=relevance_reason.strip(),
        source_validation_status=source_validation_status,
        llm_support_status=llm_support_status,
        conversion_status="not_converted",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


def convert_research_finding_to_manual_object(
    db: Session,
    case_id: UUID,
    finding_id: UUID,
    payload: ManualObjectFromSourceCreate,
) -> tuple[ResearchFindingModel, UUID, SourceReferenceModel, str, UUID]:
    finding = get_research_finding(db, case_id, finding_id)
    if finding.conversion_status == "converted":
        raise ResearchFindingValidationError("Research finding has already been converted")
    source_reference = db.get(SourceReferenceModel, finding.source_reference_id)
    if source_reference is None or source_reference.case_id != case_id:
        raise ResearchFindingValidationError("Source reference not found for this research finding")
    ensure_source_reference_document_is_active(db, case_id, source_reference, ResearchFindingValidationError)

    try:
        run_id, source_reference, object_type, object_id = create_manual_object_from_source_reference(
            db,
            case_id,
            finding.source_reference_id,
            payload,
            input_kind="manual_research_finding_conversion",
            target_source_validation_status=finding.source_validation_status,
        )
    except ManualEntryError as exc:
        raise ResearchFindingValidationError(str(exc)) from exc

    finding.conversion_status = "converted"
    finding.target_object_type = object_type
    finding.target_object_id = object_id
    finding.updated_at = datetime.now(UTC)
    db.add(finding)
    db.flush()

    event = AuditEvent(
        event_type="research_finding_converted",
        success=True,
        case_id=str(case_id),
        user_id=str(source_reference.created_by_user_id) if source_reference.created_by_user_id is not None else None,
        analysis_run_id=str(run_id),
        related_object_type="research_finding",
        related_object_id=str(finding.id),
        related_document_id=str(source_reference.document_id),
        related_page_id=str(source_reference.page_id) if source_reference.page_id is not None else None,
        related_chunk_id=str(source_reference.chunk_id) if source_reference.chunk_id is not None else None,
        input_summary={"source_reference_id": str(source_reference.id), "object_type": object_type},
        output_summary={
            "research_finding_id": str(finding.id),
            "conversion_status": finding.conversion_status,
            "target_object_type": object_type,
            "target_object_id": str(object_id),
        },
    )
    DatabaseAuditWriter(db).write(event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(event)
    db.commit()
    db.refresh(finding)
    return finding, run_id, source_reference, object_type, object_id


def set_aside_research_finding(
    db: Session,
    *,
    case_id: UUID,
    finding_id: UUID,
) -> ResearchFindingModel:
    finding = get_research_finding(db, case_id, finding_id)
    if finding.conversion_status == "converted":
        raise ResearchFindingValidationError("Converted research finding cannot be set aside")
    finding.conversion_status = "ignored"
    finding.target_object_type = None
    finding.target_object_id = None
    finding.updated_at = datetime.now(UTC)
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


def restore_research_finding(
    db: Session,
    *,
    case_id: UUID,
    finding_id: UUID,
) -> ResearchFindingModel:
    finding = get_research_finding(db, case_id, finding_id)
    if finding.conversion_status == "converted":
        raise ResearchFindingValidationError("Converted research finding cannot be restored to the worklist")
    finding.conversion_status = "not_converted"
    finding.target_object_type = None
    finding.target_object_id = None
    finding.updated_at = datetime.now(UTC)
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


def delete_research_finding(
    db: Session,
    *,
    case_id: UUID,
    finding_id: UUID,
) -> None:
    finding = get_research_finding(db, case_id, finding_id)
    if finding.conversion_status == "converted":
        raise ResearchFindingValidationError("Converted research finding cannot be deleted")
    db.delete(finding)
    db.commit()


def delete_research_findings(
    db: Session,
    *,
    case_id: UUID,
    finding_ids: list[UUID],
) -> int:
    findings = list(
        db.execute(
            select(ResearchFindingModel).where(
                ResearchFindingModel.case_id == case_id,
                ResearchFindingModel.id.in_(finding_ids),
            )
        ).scalars()
    )
    found_ids = {finding.id for finding in findings}
    missing_ids = [finding_id for finding_id in finding_ids if finding_id not in found_ids]
    if missing_ids:
        raise ResearchFindingNotFoundError("One or more research findings were not found")
    converted_ids = [finding.id for finding in findings if finding.conversion_status == "converted"]
    if converted_ids:
        raise ResearchFindingValidationError("Converted research findings cannot be deleted")
    for finding in findings:
        db.delete(finding)
    db.commit()
    return len(findings)
