from uuid import uuid4

import pytest

from app.models.document import DocumentChunkModel
from app.services.analysis_modules import (
    AnalysisModuleError,
    RetrievedChunk,
    analysis_retrieval_queries,
    parse_llm_json_object,
    validate_extracted_claims,
    validate_extracted_entities,
    validate_extracted_events,
    validate_extracted_summary_items,
)


def _retrieved_chunk(label: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        label=label,
        document_name="irat.txt",
        chunk=DocumentChunkModel(
            id=uuid4(),
            case_id=uuid4(),
            document_id=uuid4(),
            page_start=1,
            page_end=1,
            chunk_index=0,
            chunk_text=text,
            char_start=0,
            char_end=len(text),
            token_count=10,
            chunking_strategy="char_window_v1",
            chunker_version="1",
            version_no=1,
            is_current=True,
        ),
        retrieval_score=1.0,
    )


def test_parse_llm_json_object_accepts_fenced_json() -> None:
    payload = parse_llm_json_object('```json\n{"claims":[],"unsupported_claims":[]}\n```')

    assert payload["claims"] == []


def test_parse_llm_json_object_rejects_array() -> None:
    with pytest.raises(AnalysisModuleError):
        parse_llm_json_object("[]")


def test_analysis_retrieval_queries_extracts_source_like_keywords_from_hungarian_prompt() -> None:
    queries = analysis_retrieval_queries(
        "Keszits rovid forrashu ugyosszefoglalo elemeket a telefonhivasrol es a helyszinre erkezesrol."
    )

    assert queries[0].startswith("Keszits rovid")
    assert "telefonhivas" in queries
    assert "helyszin" in queries


def test_validate_extracted_claims_requires_quote_in_labeled_chunk() -> None:
    chunks = [
        _retrieved_chunk("chunk_1", "A jegyzokonyv szerint telefonhivas tortent."),
        _retrieved_chunk("chunk_2", "Masik forras masik tartalommal."),
    ]
    payload = {
        "claims": [
            {
                "claim_type": "document_fact",
                "claim_text": "Telefonhivas tortent.",
                "quote_text": "telefonhivas tortent",
                "source_label": "chunk_1",
            },
            {
                "claim_type": "document_fact",
                "claim_text": "Rossz chunk.",
                "quote_text": "telefonhivas tortent",
                "source_label": "chunk_2",
            },
        ],
        "unsupported_claims": ["nincs eleg forras"],
    }

    valid_claims, unsupported = validate_extracted_claims(payload, chunks)

    assert len(valid_claims) == 1
    assert valid_claims[0]["source_label"] == "chunk_1"
    assert unsupported == ["nincs eleg forras"]


def test_validate_extracted_claims_normalizes_unknown_claim_type() -> None:
    chunks = [_retrieved_chunk("chunk_1", "A forras szerint adat szerepel.")]
    payload = {
        "claims": [
            {
                "claim_type": "accusation",
                "claim_text": "Adat szerepel.",
                "quote_text": "adat szerepel",
                "source_label": "chunk_1",
            }
        ],
        "unsupported_claims": [],
    }

    valid_claims, _ = validate_extracted_claims(payload, chunks)

    assert valid_claims[0]["claim_type"] == "unknown"


def test_validate_extracted_events_requires_quote_in_labeled_chunk() -> None:
    chunks = [_retrieved_chunk("chunk_1", "18:42-kor telefonhivas tortent Kovacs Anna es Nagy Peter kozott.")]
    payload = {
        "events": [
            {
                "event_type": "call",
                "event_title": "Telefonhivas",
                "event_description": "A forras telefonhivast emlit.",
                "event_time_raw": "18:42-kor",
                "time_precision": "minute",
                "location_text": None,
                "quote_text": "18:42-kor telefonhivas tortent",
                "source_label": "chunk_1",
            }
        ],
        "unsupported_events": [],
    }

    valid_events, unsupported = validate_extracted_events(payload, chunks)

    assert len(valid_events) == 1
    assert valid_events[0]["event_type"] == "call"
    assert unsupported == []


def test_validate_extracted_events_normalizes_unknown_values() -> None:
    chunks = [_retrieved_chunk("chunk_1", "A forras szerint esemeny tortent.")]
    payload = {
        "events": [
            {
                "event_type": "accusation",
                "event_title": "Esemeny",
                "time_precision": "certain",
                "quote_text": "esemeny tortent",
                "source_label": "chunk_1",
            }
        ],
        "unsupported_events": ["nincs pontos ido"],
    }

    valid_events, unsupported = validate_extracted_events(payload, chunks)

    assert valid_events[0]["event_type"] == "other"
    assert valid_events[0]["time_precision"] == "unknown"
    assert unsupported == ["nincs pontos ido"]


def test_validate_extracted_entities_requires_quote_in_labeled_chunk() -> None:
    chunks = [_retrieved_chunk("chunk_1", "Kovacs Anna es Nagy Peter kozott telefonhivas tortent.")]
    payload = {
        "entities": [
            {
                "entity_type": "person",
                "canonical_name": "Kovacs Anna",
                "normalized_value": None,
                "description": None,
                "mentions": [
                    {
                        "surface_text": "Kovacs Anna",
                        "quote_text": "Kovacs Anna",
                        "source_label": "chunk_1",
                    }
                ],
            }
        ],
        "unsupported_entities": [],
    }

    valid_entities, unsupported = validate_extracted_entities(payload, chunks)

    assert len(valid_entities) == 1
    assert valid_entities[0]["entity_type"] == "person"
    assert valid_entities[0]["surface_text"] == "Kovacs Anna"
    assert unsupported == []


def test_validate_extracted_entities_normalizes_unknown_type() -> None:
    chunks = [_retrieved_chunk("chunk_1", "ABC-123 rendszam szerepel a forrasban.")]
    payload = {
        "entities": [
            {
                "entity_type": "suspect",
                "canonical_name": "ABC-123",
                "mentions": [
                    {
                        "surface_text": "ABC-123",
                        "quote_text": "ABC-123",
                        "source_label": "chunk_1",
                    }
                ],
            }
        ],
        "unsupported_entities": ["nincs szerepminosites"],
    }

    valid_entities, unsupported = validate_extracted_entities(payload, chunks)

    assert valid_entities[0]["entity_type"] == "other"
    assert unsupported == ["nincs szerepminosites"]


def test_validate_extracted_summary_items_requires_quote_in_labeled_chunk() -> None:
    chunks = [_retrieved_chunk("chunk_1", "Az irat szerint a hivas 18:42-kor tortent.")]
    payload = {
        "summary_items": [
            {
                "summary_type": "case_overview",
                "title": "Telefonhivas",
                "body_text": "A forras egy 18:42-kor tortent hivast emlit.",
                "quote_text": "hivas 18:42-kor tortent",
                "source_label": "chunk_1",
                "confidence": "medium",
                "support_type": "direct",
            }
        ],
        "unsupported_summary_items": [],
    }

    valid_items, unsupported = validate_extracted_summary_items(payload, chunks)

    assert len(valid_items) == 1
    assert valid_items[0]["summary_type"] == "case_overview"
    assert str(valid_items[0]["confidence"]) == "0.6000"
    assert unsupported == []


def test_validate_extracted_summary_items_normalizes_unknown_values() -> None:
    chunks = [_retrieved_chunk("chunk_1", "A dokumentum ugyiratot emlit.")]
    payload = {
        "summary_items": [
            {
                "summary_type": "risk_score",
                "title": "Ugyirat",
                "body_text": "A dokumentum ugyiratot emlit.",
                "quote_text": "dokumentum ugyiratot emlit",
                "source_label": "chunk_1",
                "confidence": 1.5,
                "support_type": "unsupported",
            }
        ],
        "unsupported_summary_items": ["nincs kockazati kovetkeztetes"],
    }

    valid_items, unsupported = validate_extracted_summary_items(payload, chunks)

    assert valid_items[0]["summary_type"] == "other"
    assert valid_items[0]["support_type"] == "direct"
    assert valid_items[0]["confidence"] is None
    assert unsupported == ["nincs kockazati kovetkeztetes"]
