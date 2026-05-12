from fastapi import APIRouter

from app.api.v1.analysis_modules import router as analysis_modules_router
from app.api.v1.analysis_smoke import router as analysis_smoke_router
from app.api.v1.analysis_runs import router as analysis_runs_router
from app.api.v1.cases import router as cases_router
from app.api.v1.claims import router as claims_router
from app.api.v1.documents import router as documents_router
from app.api.v1.events import router as events_router
from app.api.v1.exports import router as exports_router
from app.api.v1.review_report import router as review_report_router
from app.api.v1.search import router as search_router
from app.api.v1.source_references import router as source_references_router
from app.api.v1.system import router as system_router

api_router = APIRouter()
api_router.include_router(analysis_modules_router, tags=["analysis"])
api_router.include_router(analysis_smoke_router, tags=["analysis"])
api_router.include_router(analysis_runs_router, tags=["analysis-runs"])
api_router.include_router(cases_router, prefix="/cases", tags=["cases"])
api_router.include_router(claims_router, tags=["claims"])
api_router.include_router(documents_router, tags=["documents"])
api_router.include_router(events_router, tags=["events"])
api_router.include_router(exports_router, tags=["exports"])
api_router.include_router(review_report_router, tags=["review-report"])
api_router.include_router(search_router, tags=["search"])
api_router.include_router(source_references_router, tags=["source-references"])
api_router.include_router(system_router, prefix="/system", tags=["system"])
