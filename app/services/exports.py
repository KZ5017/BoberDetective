from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID
import hashlib
import html
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.export import ExportItemModel, ExportModel
from app.models.review import HumanReviewModel
from app.schemas.export import ExportCreate
from app.schemas.review_report import CaseReviewReport, ReviewReportItem
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.review_report import ReviewReportValidationError, build_case_review_report
from app.services.reviews import latest_review_status, list_object_reviews, record_object_review, review_status_for_action
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
    return list_object_reviews(db, "export", export_id)


def review_export(
    db: Session,
    *,
    case_id: UUID,
    export_id: UUID,
    action_type: str,
    review_comment: str | None = None,
) -> ExportModel:
    export = get_export(db, case_id, export_id)
    previous_status = latest_review_status(db, "export", export_id)
    new_status = _review_status_for_action(action_type, previous_status)

    record_object_review(
        db,
        case_id=case_id,
        object_type="export",
        object_id=export.id,
        action_type=action_type,
        previous_status=previous_status,
        new_status=new_status,
        review_comment=review_comment,
        audit_event_type="export_review_recorded",
    )
    db.commit()
    db.refresh(export)
    return export


def create_review_report_export(db: Session, case_id: UUID, payload: ExportCreate) -> ExportModel:
    if payload.export_type not in {"json", "html"} or payload.export_scope != "review_report":
        raise ExportValidationError("Only review_report JSON and HTML export are supported")

    try:
        report = build_case_review_report(db, case_id, payload.report_filters)
    except ReviewReportValidationError as exc:
        raise ExportValidationError(str(exc)) from exc
    filtered_items = _filter_report_items(report.items, payload.review_filter, payload.require_source_valid)
    content = _build_export_content(report, filtered_items, payload)
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
        export_parameters={
            "require_source_valid": payload.require_source_valid,
            "report_filters": payload.report_filters.model_dump() if payload.report_filters is not None else None,
        },
    )
    db.add(export)
    db.flush()

    export_path = _write_export_file(case_id, export.id, payload.export_type, content)
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
            "report_filters": payload.report_filters.model_dump() if payload.report_filters is not None else None,
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
            "report_filters": payload.report_filters.model_dump() if payload.report_filters is not None else None,
            "generated_at": datetime.now(UTC).isoformat(),
            "item_count": len(filtered_items),
        },
        "items": [item.model_dump(mode="json") for item in filtered_items],
    }


def _build_export_content(
    report: CaseReviewReport,
    filtered_items: list[ReviewReportItem],
    payload: ExportCreate,
) -> bytes:
    if payload.export_type == "json":
        export_payload = _build_export_payload(report, filtered_items, payload)
        return json.dumps(export_payload, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    if payload.export_type == "html":
        return _build_html_export(report, filtered_items, payload).encode("utf-8")
    raise ExportValidationError("Unsupported export type")


def _build_html_export(
    report: CaseReviewReport,
    filtered_items: list[ReviewReportItem],
    payload: ExportCreate,
) -> str:
    generated_at = datetime.now(UTC).isoformat()
    item_blocks = "\n".join(_html_item(index, item) for index, item in enumerate(filtered_items, start=1))
    return f"""<!doctype html>
<html lang="hu">
<head>
  <meta charset="utf-8">
  <title>BoberDetective review report export</title>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.45; margin: 2rem; color: #202124; }}
    header, section {{ max-width: 1100px; }}
    .meta {{ border-collapse: collapse; margin: 1rem 0 2rem; }}
    .meta th, .meta td {{ border: 1px solid #d0d7de; padding: 0.4rem 0.6rem; text-align: left; }}
    article {{ border-top: 2px solid #d0d7de; padding: 1rem 0; }}
    .label {{ color: #57606a; font-size: 0.9rem; }}
    blockquote {{ border-left: 4px solid #d0d7de; margin-left: 0; padding-left: 1rem; color: #24292f; }}
    code {{ background: #f6f8fa; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
  <header>
    <h1>BoberDetective review report export</h1>
    <table class="meta">
      <tr><th>Case ID</th><td>{_e(str(report.case_id))}</td></tr>
      <tr><th>Generated at</th><td>{_e(generated_at)}</td></tr>
      <tr><th>Export type</th><td>{_e(payload.export_type)}</td></tr>
      <tr><th>Export scope</th><td>{_e(payload.export_scope)}</td></tr>
      <tr><th>Review filter</th><td>{_e(payload.review_filter)}</td></tr>
      <tr><th>Require source valid</th><td>{_e(str(payload.require_source_valid))}</td></tr>
      <tr><th>Report filters</th><td>{_e(json.dumps(payload.report_filters.model_dump() if payload.report_filters is not None else None, sort_keys=True))}</td></tr>
      <tr><th>Item count</th><td>{len(filtered_items)}</td></tr>
    </table>
  </header>
  <section>
    {item_blocks}
  </section>
</body>
</html>
"""


def _html_item(index: int, item: ReviewReportItem) -> str:
    source_blocks = "\n".join(_html_source(source) for source in item.sources)
    reviews = ", ".join(_e(review.action_type) for review in item.reviews) or "no reviews"
    return f"""<article>
  <h2>{index}. {_e(item.object_type)}: {_e(item.title)}</h2>
  <p class="label">Object ID: <code>{_e(str(item.object_id))}</code></p>
  <p><strong>Subtype:</strong> {_e(item.subtype)} | <strong>Review:</strong> {_e(item.review_status)} | <strong>Source validation:</strong> {_e(item.source_validation_status)}</p>
  <p><strong>Analysis run:</strong> <code>{_e(str(item.created_by_analysis_run_id))}</code></p>
  <p>{_e(item.body_text or "")}</p>
  <h3>Sources</h3>
  {source_blocks}
  <p class="label">Review history: {_e(reviews)}</p>
</article>"""


def _html_source(source) -> str:
    return f"""<div>
  <p class="label">Source reference: <code>{_e(str(source.source_reference_id))}</code> | Citation: {_e(source.citation_label or "")}</p>
  <p class="label">Document: {_e(source.document_filename or "")} | Page: {_e(_fmt_optional(source.page_number))} | Chunk: {_e(_fmt_optional(source.chunk_index))}</p>
  <p class="label">Quote chars: {_e(_fmt_optional(source.quote_char_start))}-{_e(_fmt_optional(source.quote_char_end))} | Excerpt chars: {_e(_fmt_optional(source.source_text_excerpt_char_start))}-{_e(_fmt_optional(source.source_text_excerpt_char_end))}</p>
  <blockquote>{_e(source.quote_text)}</blockquote>
  <p>{_e(source.source_text_excerpt or "")}</p>
</div>"""


def _fmt_optional(value) -> str:
    return "" if value is None else str(value)


def _e(value: str) -> str:
    return html.escape(value, quote=True)


def _write_export_file(case_id: UUID, export_id: UUID, export_type: str, content: bytes) -> Path:
    export_dir = StoragePaths(get_settings().data_root).exports_dir(str(case_id))
    export_dir.mkdir(parents=True, exist_ok=True)
    export_path = export_dir / f"{export_id}.{export_type}"
    export_path.write_bytes(content)
    return export_path


def _review_status_for_action(action_type: str, previous_status: str) -> str | None:
    return review_status_for_action(action_type, previous_status, ExportValidationError)
