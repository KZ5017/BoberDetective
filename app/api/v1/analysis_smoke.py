from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analysis_smoke import SourceCitedAnalysisSmokeRequest, SourceCitedAnalysisSmokeResponse
from app.services.analysis_smoke import SourceCitedAnalysisSmokeError, run_source_cited_analysis_smoke

router = APIRouter()


@router.post("/cases/{case_id}/analysis/source-cited-smoke", response_model=SourceCitedAnalysisSmokeResponse)
def post_source_cited_analysis_smoke(
    case_id: UUID,
    payload: SourceCitedAnalysisSmokeRequest,
    db: Session = Depends(get_db),
) -> SourceCitedAnalysisSmokeResponse:
    try:
        return run_source_cited_analysis_smoke(db, case_id, payload)
    except SourceCitedAnalysisSmokeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
