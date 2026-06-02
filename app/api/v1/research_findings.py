from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.document import DocumentChunkModel, DocumentPageModel
from app.models.research_finding import ResearchFindingModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.research_finding import (
    ResearchFindingBulkDeleteRequest,
    ResearchFindingBulkDeleteResponse,
    ResearchFindingConvertRequest,
    ResearchFindingConvertResponse,
    ResearchFindingDetail,
    ResearchFindingList,
    ResearchFindingRead,
    ResearchFindingSetAsideRequest,
)
from app.schemas.source_reference import SourceReferenceRead
from app.services.research_findings import (
    ResearchFindingNotFoundError,
    ResearchFindingValidationError,
    convert_research_finding_to_manual_object,
    delete_research_finding,
    delete_research_findings,
    get_research_finding,
    list_research_findings,
    restore_research_finding,
    set_aside_research_finding,
)
from app.services.text_store import read_chunk_text_from_store, read_page_text_from_store


router = APIRouter()


@router.get("/cases/{case_id}/research-findings", response_model=ResearchFindingList)
def get_case_research_findings(case_id: UUID, db: Session = Depends(get_db)) -> ResearchFindingList:
    return ResearchFindingList(data=[_research_finding_read(db, finding) for finding in list_research_findings(db, case_id)])


@router.get("/cases/{case_id}/research-findings/{finding_id}", response_model=ResearchFindingDetail)
def get_case_research_finding(case_id: UUID, finding_id: UUID, db: Session = Depends(get_db)) -> ResearchFindingDetail:
    try:
        finding = get_research_finding(db, case_id, finding_id)
    except ResearchFindingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ResearchFindingDetail(finding=_research_finding_read(db, finding))


@router.post(
    "/cases/{case_id}/research-findings/{finding_id}/convert",
    response_model=ResearchFindingConvertResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_research_finding_conversion(
    case_id: UUID,
    finding_id: UUID,
    payload: ResearchFindingConvertRequest,
    db: Session = Depends(get_db),
) -> ResearchFindingConvertResponse:
    try:
        finding, run_id, source_reference, object_type, object_id = convert_research_finding_to_manual_object(
            db,
            case_id,
            finding_id,
            payload,
        )
    except ResearchFindingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ResearchFindingValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ResearchFindingConvertResponse(
        analysis_run_id=run_id,
        source_reference=SourceReferenceRead.model_validate(source_reference),
        object_type=object_type,
        object_id=object_id,
        finding=_research_finding_read(db, finding),
    )


@router.post("/cases/{case_id}/research-findings/{finding_id}/set-aside", response_model=ResearchFindingDetail)
def post_research_finding_set_aside(
    case_id: UUID,
    finding_id: UUID,
    payload: ResearchFindingSetAsideRequest,
    db: Session = Depends(get_db),
) -> ResearchFindingDetail:
    _ = payload
    try:
        finding = set_aside_research_finding(db, case_id=case_id, finding_id=finding_id)
    except ResearchFindingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ResearchFindingValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ResearchFindingDetail(finding=_research_finding_read(db, finding))


@router.post("/cases/{case_id}/research-findings/{finding_id}/restore", response_model=ResearchFindingDetail)
def post_research_finding_restore(
    case_id: UUID,
    finding_id: UUID,
    db: Session = Depends(get_db),
) -> ResearchFindingDetail:
    try:
        finding = restore_research_finding(db, case_id=case_id, finding_id=finding_id)
    except ResearchFindingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ResearchFindingValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ResearchFindingDetail(finding=_research_finding_read(db, finding))


@router.delete("/cases/{case_id}/research-findings/{finding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case_research_finding(case_id: UUID, finding_id: UUID, db: Session = Depends(get_db)) -> None:
    try:
        delete_research_finding(db, case_id=case_id, finding_id=finding_id)
    except ResearchFindingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ResearchFindingValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/cases/{case_id}/research-findings/bulk-delete", response_model=ResearchFindingBulkDeleteResponse)
def post_research_finding_bulk_delete(
    case_id: UUID,
    payload: ResearchFindingBulkDeleteRequest,
    db: Session = Depends(get_db),
) -> ResearchFindingBulkDeleteResponse:
    try:
        deleted_count = delete_research_findings(db, case_id=case_id, finding_ids=payload.finding_ids)
    except ResearchFindingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ResearchFindingValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ResearchFindingBulkDeleteResponse(deleted_count=deleted_count)


def _research_finding_read(db: Session, finding: ResearchFindingModel) -> ResearchFindingRead:
    source_reference = finding.source_reference
    source_read = (
        _source_reference_read_with_excerpt(
            db,
            source_reference,
            include_unresolved_context=finding.source_validation_status == "source_invalid",
        )
        if source_reference is not None
        else None
    )
    return ResearchFindingRead.model_validate(finding).model_copy(update={"source_reference": source_read})


def _source_reference_read_with_excerpt(
    db: Session,
    source_reference: SourceReferenceModel,
    *,
    include_unresolved_context: bool = False,
) -> SourceReferenceRead:
    source_text = _source_text_for_excerpt(db, source_reference)
    excerpt, excerpt_start, excerpt_end = _source_excerpt(
        source_text,
        source_reference.quote_text,
        source_reference.quote_char_start,
        source_reference.quote_char_end,
        include_unresolved_context=include_unresolved_context,
    )
    return SourceReferenceRead.model_validate(source_reference).model_copy(
        update={
            "source_text_excerpt": excerpt,
            "source_text_excerpt_char_start": excerpt_start,
            "source_text_excerpt_char_end": excerpt_end,
        }
    )


def _source_text_for_excerpt(db: Session, source_reference: SourceReferenceModel) -> str | None:
    if source_reference.chunk_id is not None:
        chunk = db.get(DocumentChunkModel, source_reference.chunk_id)
        return read_chunk_text_from_store(db, chunk) if chunk is not None else None
    if source_reference.page_id is not None:
        page = db.get(DocumentPageModel, source_reference.page_id)
        return read_page_text_from_store(db, page) if page is not None else None
    return None


def _source_excerpt(
    source_text: str | None,
    quote_text: str,
    quote_char_start: int | None,
    quote_char_end: int | None,
    *,
    include_unresolved_context: bool = False,
) -> tuple[str | None, int | None, int | None]:
    if source_text is None:
        return None, None, None
    quote_start = quote_char_start
    quote_end = quote_char_end
    if quote_start is None or quote_end is None or source_text[quote_start:quote_end] != quote_text:
        found_at = source_text.find(quote_text)
        if found_at < 0:
            if include_unresolved_context:
                return source_text, 0, len(source_text)
            return None, None, None
        quote_start = found_at
        quote_end = found_at + len(quote_text)
    return source_text, 0, len(source_text)
