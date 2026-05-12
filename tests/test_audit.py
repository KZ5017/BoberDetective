from app.services.audit import AuditEvent


def test_audit_event_serialization_is_stable() -> None:
    event = AuditEvent(event_type="case_created", success=True)

    first = event.to_json_dict()
    second = event.to_json_dict()

    assert first["id"] == second["id"]
    assert first["event_timestamp"] == second["event_timestamp"]


def test_audit_event_redacts_sensitive_keys() -> None:
    event = AuditEvent(
        event_type="llm_called",
        success=True,
        input_summary={"api_key": "secret", "nested": {"token": "secret", "safe": "value"}},
    )

    data = event.to_json_dict()

    assert data["input_summary"]["api_key"] == "[REDACTED]"
    assert data["input_summary"]["nested"]["token"] == "[REDACTED]"
    assert data["input_summary"]["nested"]["safe"] == "value"

