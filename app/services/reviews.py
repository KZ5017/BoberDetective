from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.review import HumanReviewModel
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.storage import StoragePaths
from app.services.users import get_or_create_dev_user


class ReviewValidationError(ValueError):
    pass


def list_object_reviews(db: Session, object_type: str, object_id: UUID) -> list[HumanReviewModel]:
    return list(
        db.execute(
            select(HumanReviewModel)
            .where(HumanReviewModel.object_type == object_type, HumanReviewModel.object_id == object_id)
            .order_by(HumanReviewModel.performed_at.desc())
        ).scalars()
    )


def latest_review_status(db: Session, object_type: str, object_id: UUID, default_status: str = "needs_review") -> str:
    review = db.execute(
        select(HumanReviewModel)
        .where(HumanReviewModel.object_type == object_type, HumanReviewModel.object_id == object_id)
        .order_by(HumanReviewModel.performed_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if review is None or review.new_review_status is None:
        return default_status
    return review.new_review_status


def review_status_for_action(
    action_type: str,
    previous_status: str,
    error_factory: Callable[[str], Exception] | None = None,
) -> str | None:
    if action_type == "verify":
        return "verified"
    if action_type == "reject":
        return "rejected"
    if action_type == "mark_needs_review":
        return "needs_review"
    if action_type == "comment":
        return None
    if error_factory is not None:
        raise error_factory("Unsupported review action")
    raise ReviewValidationError("Unsupported review action")


def ensure_review_status_transition(
    action_type: str,
    previous_status: str,
    new_status: str | None,
    error_factory: Callable[[str], Exception] | None = None,
) -> None:
    if new_status is None:
        return
    if new_status != previous_status:
        return
    message = "Review action would not change status"
    if error_factory is not None:
        raise error_factory(message)
    raise ReviewValidationError(message)


def record_object_review(
    db: Session,
    *,
    case_id: UUID,
    object_type: str,
    object_id: UUID,
    action_type: str,
    previous_status: str,
    new_status: str | None,
    review_comment: str | None,
    audit_event_type: str,
) -> HumanReviewModel:
    ensure_review_status_transition(action_type, previous_status, new_status)
    user = get_or_create_dev_user(db)
    review = HumanReviewModel(
        case_id=case_id,
        object_type=object_type,
        object_id=object_id,
        action_type=action_type,
        previous_review_status=previous_status,
        new_review_status=new_status,
        review_comment=review_comment,
        performed_by_user_id=user.id,
    )
    db.add(review)
    db.flush()

    audit_event = AuditEvent(
        event_type=audit_event_type,
        success=True,
        case_id=str(case_id),
        user_id=str(user.id),
        related_object_type=object_type,
        related_object_id=str(object_id),
        input_summary={"action_type": action_type, "previous_review_status": previous_status},
        output_summary={"new_review_status": new_status, "human_review_id": str(review.id)},
    )
    DatabaseAuditWriter(db).write(audit_event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(audit_event)
    return review
