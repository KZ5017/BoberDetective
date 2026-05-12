import pytest

from app.services.analysis_smoke import SourceCitedAnalysisSmokeError, _parse_smoke_json, _validate_claims


def test_parse_smoke_json_accepts_plain_object() -> None:
    payload = _parse_smoke_json('{"claims":[],"unsupported_claims":["nincs forras"]}')

    assert payload["claims"] == []


def test_parse_smoke_json_rejects_invalid_json() -> None:
    with pytest.raises(SourceCitedAnalysisSmokeError):
        _parse_smoke_json("not json")


def test_validate_claims_keeps_only_quotes_present_in_source() -> None:
    payload = {
        "claims": [
            {"claim_text": "ok", "quote_text": "pontos idezet", "source_label": "chunk_1"},
            {"claim_text": "bad", "quote_text": "hamis idezet", "source_label": "chunk_1"},
        ],
        "unsupported_claims": ["nem bizonyitott"],
    }

    valid_claims, unsupported = _validate_claims(payload, "ez egy pontos idezet a forrasban")

    assert valid_claims == [{"claim_text": "ok", "quote_text": "pontos idezet", "source_label": "chunk_1"}]
    assert unsupported == ["nem bizonyitott"]
