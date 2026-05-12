from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.audit import AuditEventModel
from app.services.storage import StoragePaths


_REDACTED_KEYS = {"api_key", "authorization", "password", "secret", "token"}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in _REDACTED_KEYS else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    success: bool
    id: UUID = field(default_factory=uuid4)
    event_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    case_id: str | None = None
    user_id: str | None = None
    analysis_run_id: str | None = None
    related_object_type: str | None = None
    related_object_id: str | None = None
    related_document_id: str | None = None
    related_page_id: str | None = None
    related_chunk_id: str | None = None
    input_summary: dict[str, Any] = field(default_factory=dict)
    output_summary: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "event_type": self.event_type,
            "event_timestamp": self.event_timestamp.isoformat(),
            "case_id": self.case_id,
            "user_id": self.user_id,
            "analysis_run_id": self.analysis_run_id,
            "related_object_type": self.related_object_type,
            "related_object_id": self.related_object_id,
            "related_document_id": self.related_document_id,
            "related_page_id": self.related_page_id,
            "related_chunk_id": self.related_chunk_id,
            "success": self.success,
            "input_summary": _redact(self.input_summary),
            "output_summary": _redact(self.output_summary),
            "error_message": self.error_message,
        }


class JsonlAuditWriter:
    def __init__(self, storage: StoragePaths) -> None:
        self._storage = storage

    def write(self, event: AuditEvent) -> Path:
        audit_dir = self._storage.audit_dir(event.case_id)
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / "audit.jsonl"
        with audit_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_json_dict(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")
        return audit_file


def _to_uuid(value: str | None) -> UUID | None:
    if value is None:
        return None
    return UUID(str(value))


class DatabaseAuditWriter:
    def __init__(self, db: Session) -> None:
        self._db = db

    def write(self, event: AuditEvent) -> AuditEventModel:
        event_data = event.to_json_dict()
        model = AuditEventModel(
            id=UUID(event_data["id"]),
            case_id=_to_uuid(event.case_id),
            user_id=_to_uuid(event.user_id),
            analysis_run_id=_to_uuid(event.analysis_run_id),
            event_type=event.event_type,
            related_object_type=event.related_object_type,
            related_object_id=_to_uuid(event.related_object_id),
            related_document_id=_to_uuid(event.related_document_id),
            related_page_id=_to_uuid(event.related_page_id),
            related_chunk_id=_to_uuid(event.related_chunk_id),
            success=event.success,
            input_summary=event_data["input_summary"],
            output_summary=event_data["output_summary"],
            error_message=event.error_message,
        )
        self._db.add(model)
        self._db.flush()
        return model
