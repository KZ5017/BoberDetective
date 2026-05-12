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


class AnalysisRunList(BaseModel):
    data: list[AnalysisRunRead]


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
    created_at: datetime


class AnalysisRunOutputRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    analysis_run_id: UUID
    output_type: str
    output_object_id: UUID
    output_position: int | None
    created_at: datetime


class AnalysisRunDetail(BaseModel):
    run: AnalysisRunRead
    inputs: list[AnalysisRunInputRead]
    outputs: list[AnalysisRunOutputRead]
