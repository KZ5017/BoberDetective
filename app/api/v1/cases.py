from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.case import CaseCreate, CaseList, CaseRead
from app.services.cases import create_case, list_cases

router = APIRouter()


@router.get("", response_model=CaseList)
def get_cases(db: Session = Depends(get_db)) -> CaseList:
    return CaseList(data=[CaseRead.model_validate(case) for case in list_cases(db)])


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
def post_case(payload: CaseCreate, db: Session = Depends(get_db)) -> CaseRead:
    case = create_case(db, payload)
    return CaseRead.model_validate(case)

