from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.documents import _document_read
from app.db.session import get_db
from app.schemas.document import DocumentList
from app.schemas.document_collection import (
    DocumentCollectionCreate,
    DocumentCollectionList,
    DocumentCollectionMembershipChangeRequest,
    DocumentCollectionMembershipChangeResponse,
    DocumentCollectionRead,
    DocumentCollectionScopeResolveRequest,
    DocumentCollectionScopeResolveResponse,
    DocumentCollectionUpdate,
)
from app.services.document_collections import (
    CaseNotFoundError,
    DocumentCollectionLimitError,
    DocumentCollectionMembershipError,
    DocumentCollectionNameConflictError,
    DocumentCollectionNotFoundError,
    DocumentCollectionScopeError,
    add_documents_to_collection,
    create_document_collection,
    delete_document_collection,
    get_collection_counts,
    list_collection_documents,
    list_document_collections,
    list_document_collections_for_document,
    remove_documents_from_collection,
    resolve_document_scope,
    update_document_collection,
)


router = APIRouter()


@router.get("/cases/{case_id}/document-collections", response_model=DocumentCollectionList)
def get_document_collections(case_id: UUID, db: Session = Depends(get_db)) -> DocumentCollectionList:
    try:
        collections = list_document_collections(db, case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DocumentCollectionList(data=[_collection_read(db, collection) for collection in collections])


@router.post("/cases/{case_id}/document-collections", response_model=DocumentCollectionRead, status_code=status.HTTP_201_CREATED)
def post_document_collection(
    case_id: UUID,
    payload: DocumentCollectionCreate,
    db: Session = Depends(get_db),
) -> DocumentCollectionRead:
    try:
        collection = create_document_collection(db, case_id, payload)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentCollectionNameConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DocumentCollectionLimitError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _collection_read(db, collection)


@router.post("/cases/{case_id}/document-collections/resolve-scope", response_model=DocumentCollectionScopeResolveResponse)
def post_document_collection_scope_resolve(
    case_id: UUID,
    payload: DocumentCollectionScopeResolveRequest,
    db: Session = Depends(get_db),
) -> DocumentCollectionScopeResolveResponse:
    try:
        resolution = resolve_document_scope(
            db,
            case_id,
            payload.source_mode,
            document_ids=payload.document_ids,
            collection_ids=payload.collection_ids,
        )
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentCollectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentCollectionScopeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return DocumentCollectionScopeResolveResponse(
        source_mode=resolution.source_mode,
        requested_document_ids=resolution.requested_document_ids,
        requested_collection_ids=resolution.requested_collection_ids,
        resolved_document_count=resolution.resolved_document_count,
        active_document_count=resolution.active_document_count,
        inactive_document_count=resolution.inactive_document_count,
        duplicate_membership_count=resolution.duplicate_membership_count,
        document_ids_preview=resolution.document_ids_preview,
        warnings=resolution.warnings,
    )


@router.patch("/cases/{case_id}/document-collections/{collection_id}", response_model=DocumentCollectionRead)
def patch_document_collection(
    case_id: UUID,
    collection_id: UUID,
    payload: DocumentCollectionUpdate,
    db: Session = Depends(get_db),
) -> DocumentCollectionRead:
    try:
        collection = update_document_collection(db, case_id, collection_id, payload)
    except DocumentCollectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentCollectionNameConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _collection_read(db, collection)


@router.delete("/cases/{case_id}/document-collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_collection_endpoint(
    case_id: UUID,
    collection_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_document_collection(db, case_id, collection_id)
    except DocumentCollectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return None


@router.get("/cases/{case_id}/document-collections/{collection_id}/documents", response_model=DocumentList)
def get_document_collection_documents(
    case_id: UUID,
    collection_id: UUID,
    db: Session = Depends(get_db),
) -> DocumentList:
    try:
        documents = list_collection_documents(db, case_id, collection_id)
    except DocumentCollectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DocumentList(data=[_document_read(db, document) for document in documents])


@router.post(
    "/cases/{case_id}/document-collections/{collection_id}/documents",
    response_model=DocumentCollectionMembershipChangeResponse,
)
def post_document_collection_documents(
    case_id: UUID,
    collection_id: UUID,
    payload: DocumentCollectionMembershipChangeRequest,
    db: Session = Depends(get_db),
) -> DocumentCollectionMembershipChangeResponse:
    try:
        result = add_documents_to_collection(db, case_id, collection_id, payload.document_ids)
    except DocumentCollectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentCollectionMembershipError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _membership_response(result)


@router.delete(
    "/cases/{case_id}/document-collections/{collection_id}/documents",
    response_model=DocumentCollectionMembershipChangeResponse,
)
def delete_document_collection_documents(
    case_id: UUID,
    collection_id: UUID,
    payload: DocumentCollectionMembershipChangeRequest,
    db: Session = Depends(get_db),
) -> DocumentCollectionMembershipChangeResponse:
    try:
        result = remove_documents_from_collection(db, case_id, collection_id, payload.document_ids)
    except DocumentCollectionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentCollectionMembershipError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _membership_response(result)


@router.get("/cases/{case_id}/documents/{document_id}/collections", response_model=DocumentCollectionList)
def get_document_collections_for_document(
    case_id: UUID,
    document_id: UUID,
    db: Session = Depends(get_db),
) -> DocumentCollectionList:
    try:
        collections = list_document_collections_for_document(db, case_id, document_id)
    except DocumentCollectionMembershipError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DocumentCollectionList(data=[_collection_read(db, collection) for collection in collections])


def _collection_read(db: Session, collection) -> DocumentCollectionRead:
    counts = get_collection_counts(db, collection.id)
    return DocumentCollectionRead(
        id=collection.id,
        case_id=collection.case_id,
        name=collection.name,
        description=collection.description,
        color=collection.color,
        sort_order=collection.sort_order,
        document_count=counts.total_document_count,
        active_document_count=counts.active_document_count,
        created_by_user_id=collection.created_by_user_id,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


def _membership_response(result) -> DocumentCollectionMembershipChangeResponse:
    return DocumentCollectionMembershipChangeResponse(
        collection_id=result.collection_id,
        requested_count=result.requested_count,
        added_count=result.added_count,
        removed_count=result.removed_count,
        already_present_count=result.already_present_count,
        not_present_count=result.not_present_count,
        skipped_count=result.skipped_count,
        skipped_reasons=result.skipped_reasons,
        active_document_count=result.active_document_count,
        total_document_count=result.total_document_count,
    )
