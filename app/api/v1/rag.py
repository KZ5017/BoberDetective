from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.rag import (
    RagQueryRequest,
    RagQueryResponse,
    RagSaveAnswerRequest,
    RagSaveAnswerResponse,
    RagSavedAnswerDetail,
    RagSavedAnswerList,
)
from app.services.rag import (
    RagConflictError,
    RagNotFoundError,
    RagValidationError,
    delete_rag_answer,
    get_rag_answer,
    list_rag_answers,
    run_rag_query,
    save_rag_answer,
)


router = APIRouter()


@router.post("/cases/{case_id}/rag/query", response_model=RagQueryResponse)
def post_rag_query(
    case_id: UUID,
    payload: RagQueryRequest,
    db: Session = Depends(get_db),
) -> RagQueryResponse:
    try:
        return run_rag_query(db, case_id, payload)
    except RagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RagValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/cases/{case_id}/rag/runs/{run_id}/save-answer", response_model=RagSaveAnswerResponse)
def post_rag_save_answer(
    case_id: UUID,
    run_id: UUID,
    payload: RagSaveAnswerRequest,
    db: Session = Depends(get_db),
) -> RagSaveAnswerResponse:
    try:
        return save_rag_answer(db, case_id, run_id, payload)
    except RagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RagConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RagValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/cases/{case_id}/rag/answers", response_model=RagSavedAnswerList)
def get_rag_answers(case_id: UUID, db: Session = Depends(get_db)) -> RagSavedAnswerList:
    return RagSavedAnswerList(data=list_rag_answers(db, case_id))


@router.get("/cases/{case_id}/rag/answers/{answer_id}", response_model=RagSavedAnswerDetail)
def get_rag_answer_detail(
    case_id: UUID,
    answer_id: UUID,
    db: Session = Depends(get_db),
) -> RagSavedAnswerDetail:
    try:
        return get_rag_answer(db, case_id, answer_id)
    except RagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/cases/{case_id}/rag/answers/{answer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rag_answer_endpoint(
    case_id: UUID,
    answer_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_rag_answer(db, case_id, answer_id)
    except RagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return None
