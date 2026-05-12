from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.analysis_modules import AnalysisModuleRunRequest, AnalysisModuleRunResponse
from app.services.analysis_module_claims import run_extract_claims, validate_extracted_claims
from app.services.analysis_module_common import AnalysisModuleError, RetrievedChunk, analysis_retrieval_queries, parse_llm_json_object
from app.services.analysis_module_contradictions import run_detect_contradiction_candidates, validate_extracted_contradiction_candidates
from app.services.analysis_module_entities import run_extract_entities, validate_extracted_entities
from app.services.analysis_module_events import run_extract_events, validate_extracted_events
from app.services.analysis_module_summaries import run_summarize_case, validate_extracted_summary_items


SUPPORTED_MODULES = {
    "extract_claims",
    "extract_events",
    "extract_entities",
    "summarize_case",
    "detect_contradiction_candidates",
}


def run_analysis_module(
    db: Session,
    case_id: UUID,
    module_key: str,
    payload: AnalysisModuleRunRequest,
) -> AnalysisModuleRunResponse:
    if module_key == "extract_claims":
        return run_extract_claims(db, case_id, payload)
    if module_key == "extract_events":
        return run_extract_events(db, case_id, payload)
    if module_key == "extract_entities":
        return run_extract_entities(db, case_id, payload)
    if module_key == "summarize_case":
        return run_summarize_case(db, case_id, payload)
    if module_key == "detect_contradiction_candidates":
        return run_detect_contradiction_candidates(db, case_id, payload)
    raise AnalysisModuleError("Unsupported analysis module")
