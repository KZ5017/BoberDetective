from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analysis_modules import AnalysisModuleRunRequest, AnalysisModuleRunResponse
from app.services.analysis_modules import AnalysisModuleError, run_analysis_module

router = APIRouter()


@router.post("/cases/{case_id}/analysis/modules/{module_key}", response_model=AnalysisModuleRunResponse)
def post_analysis_module_run(
    case_id: UUID,
    module_key: str,
    payload: AnalysisModuleRunRequest,
    db: Session = Depends(get_db),
) -> AnalysisModuleRunResponse:
    try:
        return run_analysis_module(db, case_id, module_key, payload)
    except AnalysisModuleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
