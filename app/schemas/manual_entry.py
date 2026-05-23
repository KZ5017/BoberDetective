from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.source_reference import SourceReferenceCreate, SourceReferenceRead


class ManualObjectFields(BaseModel):
    object_type: str = Field(pattern="^(claim|entity|event|missing_item_candidate)$")
    claim_type: str = Field(default="document_fact", pattern="^(witness_statement|document_fact|expert_opinion|administrative_fact|inference_candidate|unknown)$")
    claim_title: str | None = None
    claim_text: str | None = None
    entity_type: str | None = Field(
        default=None,
        pattern="^(person|organization|location|phone|email|license_plate|case_reference|money_amount|document_reference|other)$",
    )
    canonical_name: str | None = None
    normalized_value: str | None = None
    description: str | None = None
    event_type: str | None = Field(
        default=None,
        pattern="^(call|meeting|statement|transfer|search|seizure|document_created|document_received|other)$",
    )
    event_title: str | None = None
    event_description: str | None = None
    event_time_start: datetime | None = None
    time_precision: str | None = Field(default=None, pattern="^(minute|hour|day|month|year|unknown)$")
    missing_item_type: str | None = Field(
        default=None,
        pattern="^(attachment|video|expert_report|protocol|image|document_reference|other)$",
    )
    referenced_item_text: str | None = None
    confidence: Decimal | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_required_fields(self) -> "ManualObjectFields":
        if self.object_type == "claim" and (not _has_text(self.claim_title) or not _has_text(self.claim_text)):
            raise ValueError("claim_title and claim_text are required for claim")
        if self.object_type == "entity" and (not _has_text(self.entity_type) or not _has_text(self.canonical_name)):
            raise ValueError("entity_type and canonical_name are required for entity")
        if self.object_type == "event" and (not _has_text(self.event_type) or not _has_text(self.event_title)):
            raise ValueError("event_type and event_title are required for event")
        if self.object_type == "missing_item_candidate" and (
            not _has_text(self.missing_item_type) or not _has_text(self.referenced_item_text) or not _has_text(self.description)
        ):
            raise ValueError("missing_item_type, referenced_item_text and description are required for missing item candidate")
        return self


class ManualObjectCreate(ManualObjectFields):
    source_reference: SourceReferenceCreate


class ManualObjectFromSourceCreate(ManualObjectFields):
    pass


class ManualObjectCreateResponse(BaseModel):
    analysis_run_id: UUID
    source_reference: SourceReferenceRead
    object_type: str
    object_id: UUID


def _has_text(value: str | None) -> bool:
    return value is not None and value.strip() != ""
