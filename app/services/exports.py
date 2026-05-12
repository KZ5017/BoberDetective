from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.export import ExportItemModel, ExportModel
from app.models.review import HumanReviewModel
from app.schemas.export import ExportCreate
from app.schemas.review_report import CaseReviewReport, ReviewReportItem
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.review_report import build_case_review_report
from app.services.storage import StoragePaths
from app.services.users import get_or_create_dev_user


class ExportError(ValueError):
    pass


class ExportNotFoundError(ExportError):
    pass


class ExportValidationError(ExportError):
    pass


def list_exports(db: Session, case_id: UUID) -> list[ExportModel]:
    return list(
        db.execute(
            select(ExportModel)
            .where(ExportModel.case_id == case_id)
            .order_by(ExportModel.created_at.desc())
        ).scalars()
    )


def get_export(db: Session, case_id: UUID, export_id: UUID) -> ExportModel:
    export = db.get(ExportModel, export_id)
    if export is None or export.case_id != case_id:
        raise ExportNotFoundError("Export not found")
    return export


def list_export_items(db: Session, export_id: UUID) -> list[ExportItemModel]:
    return list(
        db.execute(
            select(ExportItemModel)
            .where(ExportItemModel.export_id == export_id)
            .order_by(ExportItemModel.display_order.asc())
        ).scalars()
    )


def list_export_reviews(db: Session, export_id: UUID) -> list[HumanReviewModel]:
    return list(
        db.execute(
            select(HumanReviewModel)
            .where(HumanReviewModel.object_type == "export", HumanReviewModel.object_id == export_id)
            .order_by(HumanReviewModel.performed_at.desc())
        ).scalars()
    )


def review_export(
    db: Session,
    *,
    case_id: UUID,
    export_id: UUID,
    action_type: str,
    review_comment: str | None = None,
) -> ExportModel:
    export = get_export(db, case_id, export_id)
    previous_status = _latest_export_review_status(db, export_id)
    new_status = _review_status_for_action(action_type, previous_status)
    user = get_or_create_dev_user(db)

    review = HumanReviewModel(
        case_id=case_id,
        object_type="export",
        object_id=export.id,
        action_type=action_type,
        previous_review_status=previous_status,
        new_review_status=new_status,
        review_comment=review_comment,
        performed_by_user_id=user.id,
    )
    db.add(review)
    db.flush()

    audit_event = AuditEvent(
        event_type="export_review_recorded",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="export",
        related_object_id=str(export.id),
        input_summary={"action_type": action_type, "previous_review_status": previous_status},
        output_summary={"new_review_status": new_status, "human_review_id": str(review.id)},
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(export)
    return export


def create_review_report_export(db: Session, case_id: UUID, payload: ExportCreate) -> ExportModel:
    if payload.export_type != "json" or payload.export_scope != "review_report":
        raise ExportValidationError("Only review_report JSON export is supported")

    report = build_case_review_report(db, case_id)
    filtered_items = _filter_report_items(report.items, payload.review_filter, payload.require_source_valid)
    export_payload = _build_export_payload(report, filtered_items, payload)
    content = json.dumps(export_payload, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    sha256_hash = hashlib.sha256(content).hexdigest()

    user = get_or_create_dev_user(db)
    export = ExportModel(
        case_id=case_id,
        export_type=payload.export_type,
        export_scope=payload.export_scope,
        file_path="pending",
        sha256_hash=sha256_hash,
        exported_by_user_id=user.id,
        review_filter=payload.review_filter,
        export_parameters={"require_source_valid": payload.require_source_valid},
    )
    db.add(export)
    db.flush()

    export_path = _write_export_file(case_id, export.id, content)
    export.file_path = str(export_path)
    db.add(export)

    for display_order, item in enumerate(filtered_items):
        db.add(
            ExportItemModel(
                export_id=export.id,
                object_type=item.object_type,
                object_id=item.object_id,
                source_reference_id=item.sources[0].source_reference_id if item.sources else None,
                display_order=display_order,
            )
        )
    db.flush()

    audit_event = AuditEvent(
        event_type="export_created",
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type="export",
        related_object_id=str(export.id),
        input_summary={
            "export_type": payload.export_type,
            "export_scope": payload.export_scope,
            "review_filter": payload.review_filter,
            "require_source_valid": payload.require_source_valid,
        },
        output_summary={
            "export_id": str(export.id),
            "item_count": len(filtered_items),
            "sha256_hash": sha256_hash,
        },
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    db.commit()
    db.refresh(export)
    return export


def export_file_path(export: ExportModel) -> Path:
    storage = StoragePaths(get_settings().data_root)
    path = Path(export.file_path).expanduser().resolve()
    if not StoragePaths._is_relative_to(path, storage.data_root):
        raise ExportValidationError("Export file escapes configured data root")
    if not path.exists() or not path.is_file():
        raise ExportNotFoundError("Export file not found")
    return path


def _filter_report_items(
    items: list[ReviewReportItem],
    review_filter: str,
    require_source_valid: bool,
) -> list[ReviewReportItem]:
    filtered = items
    if review_filter == "verified_only":
        filtered = [item for item in filtered if item.review_status == "verified"]
    elif review_filter == "needs_review":
        filtered = [item for item in filtered if item.review_status == "needs_review"]
    elif review_filter == "rejected":
        filtered = [item for item in filtered if item.review_status == "rejected"]
    elif review_filter != "all":
        raise ExportValidationError("Unsupported review filter")

    if require_source_valid:
        filtered = [
            item
            for item in filtered
            if item.source_validation_status == "source_valid" and len(item.sources) > 0
        ]
    return filtered


def _build_export_payload(
    report: CaseReviewReport,
    filtered_items: list[ReviewReportItem],
    payload: ExportCreate,
) -> dict:
    return {
        "export_metadata": {
            "case_id": str(report.case_id),
            "export_type": payload.export_type,
            "export_scope": payload.export_scope,
            "review_filter": payload.review_filter,
            "require_source_valid": payload.require_source_valid,
            "generated_at": datetime.now(UTC).isoformat(),
            "item_count": len(filtered_items),
        },
        "items": [item.model_dump(mode="json") for item in filtered_items],
    }


def _write_export_file(case_id: UUID, export_id: UUID, content: bytes) -> Path:
    export_dir = StoragePaths(get_settings().data_root).exports_dir(str(case_id))
    export_dir.mkdir(parents=True, exist_ok=True)
    export_path = export_dir / f"{export_id}.json"
    export_path.write_bytes(content)
    return export_path


def _latest_export_review_status(db: Session, export_id: UUID) -> str:
    review = db.execute(
        select(HumanReviewModel)
        .where(HumanReviewModel.object_type == "export", HumanReviewModel.object_id == export_id)
        .order_by(HumanReviewModel.performed_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if review is None or review.new_review_status is None:
        return "needs_review"
    return review.new_review_status


def _review_status_for_action(action_type: str, previous_status: str) -> str | None:
    if action_type == "verify":
        return "verified"
    if action_type == "reject":
        return "rejected"
    if action_type == "mark_needs_review":
        return "needs_review"
    if action_type == "comment":
        return None
    raise ExportValidationError("Unsupported export review action")
