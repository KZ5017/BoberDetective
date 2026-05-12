from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analysis import AnalysisRunDetail, AnalysisRunInputRead, AnalysisRunList, AnalysisRunOutputRead, AnalysisRunRead
from app.services.analysis_runs import (
    AnalysisRunNotFoundError,
    get_analysis_run,
    list_analysis_run_inputs,
    list_analysis_run_outputs,
    list_analysis_runs,
)

router = APIRouter()


@router.get("/cases/{case_id}/analysis-runs", response_model=AnalysisRunList)
def get_case_analysis_runs(case_id: UUID, db: Session = Depends(get_db)) -> AnalysisRunList:
    return AnalysisRunList(data=[AnalysisRunRead.model_validate(run) for run in list_analysis_runs(db, case_id)])


@router.get("/cases/{case_id}/analysis-runs/{analysis_run_id}", response_model=AnalysisRunDetail)
def get_case_analysis_run(
    case_id: UUID,
    analysis_run_id: UUID,
    db: Session = Depends(get_db),
) -> AnalysisRunDetail:
    try:
        run = get_analysis_run(db, case_id, analysis_run_id)
    except AnalysisRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AnalysisRunDetail(
        run=AnalysisRunRead.model_validate(run),
        inputs=[AnalysisRunInputRead.model_validate(item) for item in list_analysis_run_inputs(db, analysis_run_id)],
        outputs=[AnalysisRunOutputRead.model_validate(item) for item in list_analysis_run_outputs(db, analysis_run_id)],
    )
