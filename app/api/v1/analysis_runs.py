from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analysis import AnalysisRunDetail, AnalysisRunInputRead, AnalysisRunList, AnalysisRunOutputRead, AnalysisRunRead
from app.services.analysis_runs import (
    AnalysisRunNotFoundError,
    analysis_input_source_summary,
    analysis_output_summary,
    get_analysis_run,
    list_analysis_run_inputs,
    list_analysis_run_outputs,
    list_analysis_runs,
)

router = APIRouter()


@router.get("/cases/{case_id}/analysis-runs", response_model=AnalysisRunList)
def get_case_analysis_runs(case_id: UUID, db: Session = Depends(get_db)) -> AnalysisRunList:
    return AnalysisRunList(
        data=[
            AnalysisRunRead.model_validate(run).model_copy(update={"display_label": _analysis_run_display_label(db, run.id, run.run_type, run.input_parameters)})
            for run in list_analysis_runs(db, case_id)
        ]
    )


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
        inputs=[
            AnalysisRunInputRead.model_validate(item).model_copy(
                update={"source_summary": analysis_input_source_summary(db, item)}
            )
            for item in list_analysis_run_inputs(db, analysis_run_id)
        ],
        outputs=[
            AnalysisRunOutputRead.model_validate(item).model_copy(
                update={"output_summary": analysis_output_summary(db, item)}
            )
            for item in list_analysis_run_outputs(db, analysis_run_id)
        ],
    )


def _analysis_run_display_label(db: Session, analysis_run_id: UUID, run_type: str, input_parameters: dict | None) -> str | None:
    if run_type == "search_findings" and isinstance(input_parameters, dict):
        query = input_parameters.get("query")
        return str(query).strip() if isinstance(query, str) and query.strip() else None
    if run_type != "manual_entry":
        return None
    for output in list_analysis_run_outputs(db, analysis_run_id):
        if output.output_type == "source_reference":
            continue
        summary = analysis_output_summary(db, output)
        if summary is not None and summary.title:
            return summary.title
    return None
