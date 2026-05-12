from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.case import CaseModel, CaseUserModel
from app.schemas.case import CaseCreate
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.storage import StoragePaths
from app.services.users import get_or_create_dev_user


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

