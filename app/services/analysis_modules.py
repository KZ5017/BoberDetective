from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.analysis_modules import AnalysisModuleRunRequest, AnalysisModuleRunResponse
from app.services.analysis_module_common import AnalysisModuleError, RetrievedChunk, analysis_retrieval_queries, parse_llm_json_object
from app.services.analysis_module_contradictions import run_detect_contradiction_candidates, validate_extracted_contradiction_candidates
from app.services.analysis_module_findings import run_search_findings, validate_extracted_findings


SUPPORTED_MODULES = {
    "detect_contradiction_candidates",
    "search_findings",
}


def run_analysis_module(
    db: Session,
    case_id: UUID,
    module_key: str,
    payload: AnalysisModuleRunRequest,
) -> AnalysisModuleRunResponse:
    if module_key == "detect_contradiction_candidates":
        return run_detect_contradiction_candidates(db, case_id, payload)
    if module_key == "search_findings":
        return run_search_findings(db, case_id, payload)
    raise AnalysisModuleError("Unsupported analysis module")
