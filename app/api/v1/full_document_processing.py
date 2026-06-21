from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.full_document_processing import (
    DocumentProcessingItemBulkDeleteRequest,
    DocumentProcessingItemBulkDeleteResponse,
    DocumentProcessingItemDetail,
    DocumentProcessingItemList,
    DocumentProcessingItemRead,
    DocumentProcessingItemUpdateRequest,
    FullDocumentAnswerList,
    FullDocumentAnswerRead,
    FullDocumentProcessingProfileList,
    FullDocumentProcessingProfileRead,
    FullDocumentProcessingRunRequest,
    FullDocumentProcessingRunResponse,
)
from app.services.full_document_processing import (
    FullDocumentProcessingNotFoundError,
    FullDocumentProcessingValidationError,
    bulk_delete_document_processing_items,
    delete_full_document_answer,
    document_processing_item_reads,
    get_full_document_answer,
    list_document_processing_items,
    list_full_document_answers,
    list_profiles,
    run_full_document_processing,
    update_document_processing_item_status,
)


router = APIRouter()


@router.get("/full-document-processing/profiles", response_model=FullDocumentProcessingProfileList)
def get_full_document_processing_profiles() -> FullDocumentProcessingProfileList:
    return FullDocumentProcessingProfileList(
        data=[
            FullDocumentProcessingProfileRead(
                key=profile.key,
                label=profile.label,
                description=profile.description,
                item_kinds=list(profile.item_kinds),
            )
            for profile in list_profiles()
        ]
    )


@router.get(
    "/cases/{case_id}/documents/{document_id}/full-document-processing/items",
    response_model=DocumentProcessingItemList,
)
def get_document_processing_items(
    case_id: UUID,
    document_id: UUID,
    profile_key: str | None = Query(default=None),
    work_status: str | None = Query(default=None),
    item_kind: str | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> DocumentProcessingItemList:
    try:
        items = list_document_processing_items(
            db,
            case_id=case_id,
            document_id=document_id,
            profile_key=profile_key,
            work_status=work_status,
            item_kind=item_kind,
            search=search,
        )
    except FullDocumentProcessingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FullDocumentProcessingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return DocumentProcessingItemList(data=document_processing_item_reads(items))


@router.post(
    "/cases/{case_id}/documents/{document_id}/full-document-processing/runs",
    response_model=FullDocumentProcessingRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_full_document_processing_run(
    case_id: UUID,
    document_id: UUID,
    payload: FullDocumentProcessingRunRequest,
    db: Session = Depends(get_db),
) -> FullDocumentProcessingRunResponse:
    try:
        return run_full_document_processing(db, case_id=case_id, document_id=document_id, payload=payload)
    except FullDocumentProcessingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FullDocumentProcessingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/cases/{case_id}/documents/{document_id}/full-document-processing/answers",
    response_model=FullDocumentAnswerList,
)
def get_full_document_answers(
    case_id: UUID,
    document_id: UUID,
    answer_status: str = Query(default="active"),
    db: Session = Depends(get_db),
) -> FullDocumentAnswerList:
    try:
        answers = list_full_document_answers(db, case_id=case_id, document_id=document_id, answer_status=answer_status)
    except FullDocumentProcessingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FullDocumentProcessingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return FullDocumentAnswerList(data=[FullDocumentAnswerRead.model_validate(answer) for answer in answers])


@router.get(
    "/cases/{case_id}/full-document-processing/answers/{answer_id}",
    response_model=FullDocumentAnswerRead,
)
def get_full_document_answer_detail(
    case_id: UUID,
    answer_id: UUID,
    db: Session = Depends(get_db),
) -> FullDocumentAnswerRead:
    try:
        return FullDocumentAnswerRead.model_validate(get_full_document_answer(db, case_id=case_id, answer_id=answer_id))
    except FullDocumentProcessingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/cases/{case_id}/full-document-processing/answers/{answer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_full_document_answer_endpoint(
    case_id: UUID,
    answer_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_full_document_answer(db, case_id=case_id, answer_id=answer_id)
    except FullDocumentProcessingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return None


@router.post(
    "/cases/{case_id}/full-document-processing/items/bulk-delete",
    response_model=DocumentProcessingItemBulkDeleteResponse,
)
def post_document_processing_item_bulk_delete(
    case_id: UUID,
    payload: DocumentProcessingItemBulkDeleteRequest,
    db: Session = Depends(get_db),
) -> DocumentProcessingItemBulkDeleteResponse:
    try:
        deleted_count = bulk_delete_document_processing_items(db, case_id=case_id, item_ids=payload.item_ids)
    except FullDocumentProcessingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FullDocumentProcessingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return DocumentProcessingItemBulkDeleteResponse(deleted_count=deleted_count)


@router.patch(
    "/cases/{case_id}/full-document-processing/items/{item_id}",
    response_model=DocumentProcessingItemDetail,
)
def patch_document_processing_item(
    case_id: UUID,
    item_id: UUID,
    payload: DocumentProcessingItemUpdateRequest,
    db: Session = Depends(get_db),
) -> DocumentProcessingItemDetail:
    try:
        item = update_document_processing_item_status(db, case_id=case_id, item_id=item_id, work_status=payload.work_status)
    except FullDocumentProcessingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FullDocumentProcessingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return DocumentProcessingItemDetail(item=DocumentProcessingItemRead.model_validate(item))
