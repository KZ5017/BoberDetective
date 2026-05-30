from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.case import CaseCreate, CaseDeleteResponse, CaseList, CaseRead
from app.services.cases import CaseDeletionError, CaseNotFoundError, create_case, delete_case_permanently, list_cases

router = APIRouter()


@router.get("", response_model=CaseList)
def get_cases(db: Session = Depends(get_db)) -> CaseList:
    return CaseList(data=[CaseRead.model_validate(case) for case in list_cases(db)])


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
def post_case(payload: CaseCreate, db: Session = Depends(get_db)) -> CaseRead:
    case = create_case(db, payload)
    return CaseRead.model_validate(case)


@router.delete("/{case_id}", response_model=CaseDeleteResponse)
def delete_case(case_id: UUID, db: Session = Depends(get_db)) -> CaseDeleteResponse:
    try:
        result = delete_case_permanently(db, case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CaseDeletionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return CaseDeleteResponse.model_validate(result)
