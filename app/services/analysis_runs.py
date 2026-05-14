from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analysis import AnalysisRunInputModel, AnalysisRunModel, AnalysisRunOutputModel
from app.models.case import CaseModel
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.storage import StoragePaths
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
