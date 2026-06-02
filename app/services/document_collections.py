from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.case import CaseModel
from app.models.document import DocumentModel
from app.models.document_collection import DocumentCollectionMembershipModel, DocumentCollectionModel
from app.schemas.document_collection import DocumentCollectionCreate, DocumentCollectionUpdate, SourceScopeMode
from app.services.audit import AuditEvent, DatabaseAuditWriter, JsonlAuditWriter
from app.services.storage import StoragePaths
from app.services.users import get_or_create_dev_user


MAX_COLLECTIONS_PER_CASE = 500
MAX_BULK_DOCUMENTS = 5000
MAX_RESOLVED_ACTIVE_DOCUMENTS = 5000
SCOPE_PREVIEW_LIMIT = 50


class DocumentCollectionError(Exception):
    pass


class CaseNotFoundError(DocumentCollectionError):
    pass


class DocumentCollectionNotFoundError(DocumentCollectionError):
    pass


class DocumentCollectionNameConflictError(DocumentCollectionError):
    pass


class DocumentCollectionLimitError(DocumentCollectionError):
    pass


class DocumentCollectionMembershipError(DocumentCollectionError):
    pass


class DocumentCollectionScopeError(DocumentCollectionError):
    pass


@dataclass(frozen=True)
class CollectionCounts:
    total_document_count: int
    active_document_count: int


@dataclass(frozen=True)
class MembershipChangeResult:
    collection_id: UUID
    requested_count: int
    added_count: int = 0
    removed_count: int = 0
    already_present_count: int = 0
    not_present_count: int = 0
    skipped_reasons: list[str] = field(default_factory=list)
    active_document_count: int = 0
    total_document_count: int = 0

    @property
    def skipped_count(self) -> int:
        return len(self.skipped_reasons)


@dataclass(frozen=True)
class ScopeResolution:
    source_mode: SourceScopeMode
    requested_document_ids: list[UUID]
    requested_collection_ids: list[UUID]
    resolved_document_ids: list[UUID]
    inactive_document_count: int
    duplicate_membership_count: int
    warnings: list[str]

    @property
    def active_document_count(self) -> int:
        return len(self.resolved_document_ids)

    @property
    def resolved_document_count(self) -> int:
        return len(self.resolved_document_ids)

    @property
    def document_ids_preview(self) -> list[UUID]:
        return self.resolved_document_ids[:SCOPE_PREVIEW_LIMIT]


def list_document_collections(db: Session, case_id: UUID) -> list[DocumentCollectionModel]:
    _require_case(db, case_id)
    return list(
        db.execute(
            select(DocumentCollectionModel)
            .where(DocumentCollectionModel.case_id == case_id)
            .order_by(DocumentCollectionModel.sort_order, func.lower(DocumentCollectionModel.name), DocumentCollectionModel.id)
        )
        .scalars()
        .all()
    )


def create_document_collection(db: Session, case_id: UUID, payload: DocumentCollectionCreate) -> DocumentCollectionModel:
    _require_case(db, case_id)
    if _collection_count(db, case_id) >= MAX_COLLECTIONS_PER_CASE:
        raise DocumentCollectionLimitError(f"Case can have at most {MAX_COLLECTIONS_PER_CASE} document collections")
    _ensure_name_available(db, case_id, payload.name)

    user = get_or_create_dev_user(db)
    now = datetime.now(UTC)
    collection = DocumentCollectionModel(
        case_id=case_id,
        name=payload.name,
        description=payload.description,
        color=payload.color,
        sort_order=payload.sort_order,
        created_by_user_id=user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(collection)
    db.flush()
    _write_audit(
        db,
        event_type="document_collection_created",
        case_id=case_id,
        user_id=user.id,
        collection_id=collection.id,
        input_summary={"name": collection.name, "sort_order": collection.sort_order},
        output_summary={"created": True},
    )
    db.commit()
    db.refresh(collection)
    return collection


def update_document_collection(
    db: Session,
    case_id: UUID,
    collection_id: UUID,
    payload: DocumentCollectionUpdate,
) -> DocumentCollectionModel:
    collection = _require_collection(db, case_id, collection_id)
    previous = {
        "name": collection.name,
        "description": collection.description,
        "color": collection.color,
        "sort_order": collection.sort_order,
    }

    update_fields = payload.model_fields_set
    if "name" in update_fields and payload.name is not None and _normalized_name(payload.name) != _normalized_name(collection.name):
        _ensure_name_available(db, case_id, payload.name, exclude_collection_id=collection.id)
        collection.name = payload.name
    if "description" in update_fields:
        collection.description = payload.description
    if "color" in update_fields:
        collection.color = payload.color
    if "sort_order" in update_fields and payload.sort_order is not None:
        collection.sort_order = payload.sort_order
    collection.updated_at = datetime.now(UTC)

    user = get_or_create_dev_user(db)
    _write_audit(
        db,
        event_type="document_collection_updated",
        case_id=case_id,
        user_id=user.id,
        collection_id=collection.id,
        input_summary=previous,
        output_summary={
            "name": collection.name,
            "description": collection.description,
            "color": collection.color,
            "sort_order": collection.sort_order,
        },
    )
    db.commit()
    db.refresh(collection)
    return collection


def delete_document_collection(db: Session, case_id: UUID, collection_id: UUID) -> None:
    collection = _require_collection(db, case_id, collection_id)
    user = get_or_create_dev_user(db)
    counts = get_collection_counts(db, collection.id)
    db.delete(collection)
    _write_audit(
        db,
        event_type="document_collection_deleted",
        case_id=case_id,
        user_id=user.id,
        collection_id=collection_id,
        input_summary={"name": collection.name},
        output_summary={"deleted": True, "removed_memberships": counts.total_document_count},
    )
    db.commit()


def list_collection_documents(db: Session, case_id: UUID, collection_id: UUID) -> list[DocumentModel]:
    _require_collection(db, case_id, collection_id)
    return list(
        db.execute(
            select(DocumentModel)
            .join(DocumentCollectionMembershipModel, DocumentCollectionMembershipModel.document_id == DocumentModel.id)
            .where(DocumentCollectionMembershipModel.collection_id == collection_id)
            .order_by(DocumentModel.original_filename, DocumentModel.id)
        )
        .scalars()
        .all()
    )


def add_documents_to_collection(
    db: Session,
    case_id: UUID,
    collection_id: UUID,
    document_ids: list[UUID],
) -> MembershipChangeResult:
    if len(document_ids) > MAX_BULK_DOCUMENTS:
        raise DocumentCollectionMembershipError(f"At most {MAX_BULK_DOCUMENTS} documents can be changed at once")
    collection = _require_collection(db, case_id, collection_id)
    user = get_or_create_dev_user(db)
    unique_document_ids = _unique_uuids(document_ids)
    skipped_reasons: list[str] = []
    valid_count = 0
    added_count = 0
    already_present_count = 0

    for document_id in unique_document_ids:
        document = db.get(DocumentModel, document_id)
        if document is None:
            skipped_reasons.append(f"{document_id}: document_not_found")
            continue
        if document.case_id != case_id:
            skipped_reasons.append(f"{document_id}: document_not_in_case")
            continue
        valid_count += 1
        membership = db.get(DocumentCollectionMembershipModel, (collection.id, document.id))
        if membership is not None:
            already_present_count += 1
            continue
        db.add(
            DocumentCollectionMembershipModel(
                collection_id=collection.id,
                document_id=document.id,
                added_by_user_id=user.id,
                added_at=datetime.now(UTC),
            )
        )
        added_count += 1

    if valid_count == 0:
        raise DocumentCollectionMembershipError("No valid case documents were provided")

    collection.updated_at = datetime.now(UTC)
    db.flush()
    counts = get_collection_counts(db, collection.id)
    _write_audit(
        db,
        event_type="document_collection_documents_added",
        case_id=case_id,
        user_id=user.id,
        collection_id=collection.id,
        input_summary={"requested_count": len(document_ids), "unique_requested_count": len(unique_document_ids)},
        output_summary={
            "added_count": added_count,
            "already_present_count": already_present_count,
            "skipped_count": len(skipped_reasons),
        },
    )
    db.commit()
    return MembershipChangeResult(
        collection_id=collection.id,
        requested_count=len(document_ids),
        added_count=added_count,
        already_present_count=already_present_count,
        skipped_reasons=skipped_reasons,
        active_document_count=counts.active_document_count,
        total_document_count=counts.total_document_count,
    )


def remove_documents_from_collection(
    db: Session,
    case_id: UUID,
    collection_id: UUID,
    document_ids: list[UUID],
) -> MembershipChangeResult:
    if len(document_ids) > MAX_BULK_DOCUMENTS:
        raise DocumentCollectionMembershipError(f"At most {MAX_BULK_DOCUMENTS} documents can be changed at once")
    collection = _require_collection(db, case_id, collection_id)
    user = get_or_create_dev_user(db)
    unique_document_ids = _unique_uuids(document_ids)
    skipped_reasons: list[str] = []
    valid_count = 0
    removed_count = 0
    not_present_count = 0

    for document_id in unique_document_ids:
        document = db.get(DocumentModel, document_id)
        if document is None:
            skipped_reasons.append(f"{document_id}: document_not_found")
            continue
        if document.case_id != case_id:
            skipped_reasons.append(f"{document_id}: document_not_in_case")
            continue
        valid_count += 1
        membership = db.get(DocumentCollectionMembershipModel, (collection.id, document.id))
        if membership is None:
            not_present_count += 1
            continue
        db.delete(membership)
        removed_count += 1

    if valid_count == 0:
        raise DocumentCollectionMembershipError("No valid case documents were provided")

    collection.updated_at = datetime.now(UTC)
    db.flush()
    counts = get_collection_counts(db, collection.id)
    _write_audit(
        db,
        event_type="document_collection_documents_removed",
        case_id=case_id,
        user_id=user.id,
        collection_id=collection.id,
        input_summary={"requested_count": len(document_ids), "unique_requested_count": len(unique_document_ids)},
        output_summary={
            "removed_count": removed_count,
            "not_present_count": not_present_count,
            "skipped_count": len(skipped_reasons),
        },
    )
    db.commit()
    return MembershipChangeResult(
        collection_id=collection.id,
        requested_count=len(document_ids),
        removed_count=removed_count,
        not_present_count=not_present_count,
        skipped_reasons=skipped_reasons,
        active_document_count=counts.active_document_count,
        total_document_count=counts.total_document_count,
    )


def list_document_collections_for_document(db: Session, case_id: UUID, document_id: UUID) -> list[DocumentCollectionModel]:
    document = db.get(DocumentModel, document_id)
    if document is None or document.case_id != case_id:
        raise DocumentCollectionMembershipError("Document was not found in this case")
    return list(
        db.execute(
            select(DocumentCollectionModel)
            .join(DocumentCollectionMembershipModel, DocumentCollectionMembershipModel.collection_id == DocumentCollectionModel.id)
            .where(DocumentCollectionMembershipModel.document_id == document_id)
            .where(DocumentCollectionModel.case_id == case_id)
            .order_by(DocumentCollectionModel.sort_order, func.lower(DocumentCollectionModel.name), DocumentCollectionModel.id)
        )
        .scalars()
        .all()
    )


def resolve_document_scope(
    db: Session,
    case_id: UUID,
    source_mode: SourceScopeMode,
    document_ids: list[UUID] | None = None,
    collection_ids: list[UUID] | None = None,
) -> ScopeResolution:
    _require_case(db, case_id)
    document_ids = document_ids or []
    collection_ids = collection_ids or []
    warnings: list[str] = []
    duplicate_membership_count = 0
    candidate_document_ids: list[UUID] = []

    if source_mode == "case":
        candidate_document_ids = [
            item
            for item in db.execute(select(DocumentModel.id).where(DocumentModel.case_id == case_id)).scalars().all()
        ]
    elif source_mode == "documents":
        candidate_document_ids = _unique_uuids(document_ids)
        duplicate_membership_count = len(document_ids) - len(candidate_document_ids)
    elif source_mode == "collections":
        unique_collection_ids = _unique_uuids(collection_ids)
        for collection_id in unique_collection_ids:
            _require_collection(db, case_id, collection_id)
        membership_document_ids = list(
            db.execute(
                select(DocumentCollectionMembershipModel.document_id).where(
                    DocumentCollectionMembershipModel.collection_id.in_(unique_collection_ids)
                )
            )
            .scalars()
            .all()
        )
        candidate_document_ids = _unique_uuids(membership_document_ids)
        duplicate_membership_count = len(membership_document_ids) - len(candidate_document_ids)
    else:
        raise DocumentCollectionScopeError(f"Unsupported source mode: {source_mode}")

    active_document_ids: list[UUID] = []
    inactive_document_count = 0
    for document in _documents_by_ids(db, candidate_document_ids):
        if document.case_id != case_id:
            warnings.append(f"{document.id}: document_not_in_case")
            continue
        if document.lifecycle_status == "active":
            active_document_ids.append(document.id)
        else:
            inactive_document_count += 1

    found_ids = {document.id for document in _documents_by_ids(db, candidate_document_ids)}
    for missing_id in [item for item in candidate_document_ids if item not in found_ids]:
        warnings.append(f"{missing_id}: document_not_found")

    if not active_document_ids:
        raise DocumentCollectionScopeError("The resolved source scope contains no active documents")
    if len(active_document_ids) > MAX_RESOLVED_ACTIVE_DOCUMENTS:
        raise DocumentCollectionScopeError(f"The resolved source scope exceeds {MAX_RESOLVED_ACTIVE_DOCUMENTS} active documents")

    active_document_ids = sorted(active_document_ids, key=str)
    return ScopeResolution(
        source_mode=source_mode,
        requested_document_ids=document_ids,
        requested_collection_ids=collection_ids,
        resolved_document_ids=active_document_ids,
        inactive_document_count=inactive_document_count,
        duplicate_membership_count=duplicate_membership_count,
        warnings=warnings,
    )


def get_collection_counts(db: Session, collection_id: UUID) -> CollectionCounts:
    total = db.execute(
        select(func.count())
        .select_from(DocumentCollectionMembershipModel)
        .where(DocumentCollectionMembershipModel.collection_id == collection_id)
    ).scalar_one()
    active = db.execute(
        select(func.count())
        .select_from(DocumentCollectionMembershipModel)
        .join(DocumentModel, DocumentModel.id == DocumentCollectionMembershipModel.document_id)
        .where(DocumentCollectionMembershipModel.collection_id == collection_id)
        .where(DocumentModel.lifecycle_status == "active")
    ).scalar_one()
    return CollectionCounts(total_document_count=int(total), active_document_count=int(active))


def _require_case(db: Session, case_id: UUID) -> CaseModel:
    case = db.get(CaseModel, case_id)
    if case is None:
        raise CaseNotFoundError("Case was not found")
    return case


def _require_collection(db: Session, case_id: UUID, collection_id: UUID) -> DocumentCollectionModel:
    collection = db.get(DocumentCollectionModel, collection_id)
    if collection is None or collection.case_id != case_id:
        raise DocumentCollectionNotFoundError("Document collection was not found in this case")
    return collection


def _collection_count(db: Session, case_id: UUID) -> int:
    return int(
        db.execute(
            select(func.count()).select_from(DocumentCollectionModel).where(DocumentCollectionModel.case_id == case_id)
        ).scalar_one()
    )


def _ensure_name_available(
    db: Session,
    case_id: UUID,
    name: str,
    exclude_collection_id: UUID | None = None,
) -> None:
    statement = (
        select(DocumentCollectionModel)
        .where(DocumentCollectionModel.case_id == case_id)
        .where(func.lower(DocumentCollectionModel.name) == _normalized_name(name))
    )
    if exclude_collection_id is not None:
        statement = statement.where(DocumentCollectionModel.id != exclude_collection_id)
    existing = db.execute(statement).scalar_one_or_none()
    if existing is not None:
        raise DocumentCollectionNameConflictError("Document collection name already exists in this case")


def _documents_by_ids(db: Session, document_ids: list[UUID]) -> list[DocumentModel]:
    if not document_ids:
        return []
    return list(db.execute(select(DocumentModel).where(DocumentModel.id.in_(document_ids))).scalars().all())


def _unique_uuids(values: list[UUID]) -> list[UUID]:
    seen: set[UUID] = set()
    result: list[UUID] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _normalized_name(name: str) -> str:
    return name.strip().lower()


def _write_audit(
    db: Session,
    *,
    event_type: str,
    case_id: UUID,
    user_id: UUID,
    collection_id: UUID,
    input_summary: dict,
    output_summary: dict,
) -> None:
    event = AuditEvent(
        event_type=event_type,
        success=True,
        case_id=str(case_id),
        user_id=str(user_id),
        related_object_type="document_collection",
        related_object_id=str(collection_id),
        input_summary=input_summary,
        output_summary=output_summary,
    )
    DatabaseAuditWriter(db).write(event)
    JsonlAuditWriter(StoragePaths(get_settings().data_root)).write(event)
