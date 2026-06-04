from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AnalysisRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    run_type: str
    status: str
    started_by_user_id: UUID
    started_at: datetime
    finished_at: datetime | None
    provider_type: str | None
    model_name: str | None
    model_version: str | None
    prompt_template_name: str | None
    prompt_template_version: str | None
    input_parameters: dict | None
    output_schema_name: str | None
    output_schema_version: str | None
    retrieval_strategy: str | None
    validation_status: str | None
    error_message: str | None
    created_at: datetime
    display_label: str | None = None


class AnalysisRunList(BaseModel):
    data: list[AnalysisRunRead]


class AnalysisRunSourceSummary(BaseModel):
    document_filename: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    chunk_index: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    text_preview: str | None = None


class AnalysisRunInputRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    analysis_run_id: UUID
    input_type: str
    document_id: UUID | None
    page_id: UUID | None
    chunk_id: UUID | None
    related_object_type: str | None
    related_object_id: UUID | None
    sequence_no: int
    payload_json: dict | None
    source_summary: AnalysisRunSourceSummary | None = None
    created_at: datetime


class AnalysisRunOutputSummary(BaseModel):
    title: str | None = None
    body_text: str | None = None
    review_status: str | None = None
    source_validation_status: str | None = None
    source_count: int | None = None
    source_reference_id: UUID | None = None
    document_id: UUID | None = None
    document_filename: str | None = None
    page_id: UUID | None = None
    chunk_id: UUID | None = None
    page_number: int | None = None
    chunk_index: int | None = None
    citation_label: str | None = None
    quote_text: str | None = None


class AnalysisRunOutputRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    analysis_run_id: UUID
    output_type: str
    output_object_id: UUID
    output_position: int | None
    output_summary: AnalysisRunOutputSummary | None = None
    created_at: datetime


class AnalysisRunDetail(BaseModel):
    run: AnalysisRunRead
    inputs: list[AnalysisRunInputRead]
    outputs: list[AnalysisRunOutputRead]
