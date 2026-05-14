from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.document import DocumentChunkModel
from app.models.claim import ClaimModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.analysis_modules import AnalysisModuleRunRequest
from app.services import analysis_module_contradictions
from app.services import analysis_module_common
from app.services.analysis_module_contradictions import (
    ClaimPair,
    RetrievedClaim,
    build_detect_contradictions_user_prompt,
    claim_review_statuses_for_scope,
    select_claim_pairs_for_contradiction_detection,
)
from app.services.analysis_module_claims import build_extract_claims_user_prompt
from app.services.analysis_modules import (
    AnalysisModuleError,
    RetrievedChunk,
    analysis_retrieval_queries,
    parse_llm_json_object,
    validate_extracted_claims,
    validate_extracted_contradiction_candidates,
    validate_extracted_entities,
    validate_extracted_events,
    validate_extracted_missing_item_candidates,
    validate_extracted_summary_items,
)
from app.services.analysis_module_events import build_extract_events_user_prompt
from app.services.analysis_module_entities import build_extract_entities_user_prompt
from app.services.analysis_module_summaries import build_summarize_case_user_prompt
from app.services.analysis_module_missing_items import build_detect_missing_items_user_prompt


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


def _retrieved_claim(label: str, text: str) -> RetrievedClaim:
    claim_id = uuid4()
    return RetrievedClaim(
        label=label,
        claim=ClaimModel(
            id=claim_id,
            case_id=uuid4(),
            claim_type="document_fact",
            claim_text=text,
            created_by_analysis_run_id=uuid4(),
            source_validation_status="source_valid",
            review_status="needs_review",
        ),
        source_reference=SourceReferenceModel(
            id=uuid4(),
            case_id=uuid4(),
            document_id=uuid4(),
            chunk_id=uuid4(),
            quote_text=text,
            source_kind="chunk_quote",
        ),
    )


def test_parse_llm_json_object_accepts_fenced_json() -> None:
    payload = parse_llm_json_object('```json\n{"claims":[],"unsupported_claims":[]}\n```')

    assert payload["claims"] == []


def test_parse_llm_json_object_accepts_extra_text_around_json_object() -> None:
    payload = parse_llm_json_object('Rendben.\n{"claims":[],"unsupported_claims":[]}\nKesz.')

    assert payload["unsupported_claims"] == []


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


def test_analysis_retrieval_queries_strips_common_hungarian_accusative_suffixes() -> None:
    queries = analysis_retrieval_queries("Keress hivatkozott mellekletet es kamerafelvetelt.")

    assert "melleklet" in queries
    assert "kamerafelvetel" in queries
    assert "keress" not in queries
    assert "hivatkozott" not in queries


def test_retrieve_chunks_falls_back_to_case_chunks_when_keyword_search_has_no_hits(monkeypatch) -> None:
    case_id = uuid4()
    chunk = DocumentChunkModel(
        id=uuid4(),
        case_id=case_id,
        document_id=uuid4(),
        page_start=1,
        page_end=1,
        chunk_index=0,
        chunk_text="A forras szerint Kovacs Anna nyitotta ki az ajtot.",
        char_start=0,
        char_end=52,
        token_count=8,
        chunking_strategy="char_window_v1",
        chunker_version="1",
        version_no=1,
        is_current=True,
    )
    db = SimpleNamespace(execute=lambda stmt: [SimpleNamespace(DocumentChunkModel=chunk, original_filename="irat.txt")])
    monkeypatch.setattr(analysis_module_common, "keyword_search", lambda *args, **kwargs: [])

    retrieved = analysis_module_common.retrieve_chunks(
        db,
        case_id,
        AnalysisModuleRunRequest(query="Keszits rovid ugyosszefoglalot.", limit=5),
    )

    assert len(retrieved) == 1
    assert retrieved[0].chunk == chunk
    assert retrieved[0].document_name == "irat.txt"
    assert retrieved[0].retrieval_score == 0.0


def test_retrieve_chunks_requires_query_for_focused_mode() -> None:
    with pytest.raises(AnalysisModuleError):
        analysis_module_common.retrieve_chunks(
            SimpleNamespace(),
            uuid4(),
            AnalysisModuleRunRequest(source_mode="focused_query", query=None),
        )


def test_select_source_chunks_supports_document_mode_without_query() -> None:
    case_id = uuid4()
    document_id = uuid4()
    chunks = [
        DocumentChunkModel(
            id=uuid4(),
            case_id=case_id,
            document_id=document_id,
            page_start=1,
            page_end=1,
            chunk_index=index,
            chunk_text=f"A forras {index}. allitasa.",
            char_start=0,
            char_end=20,
            token_count=5,
            chunking_strategy="char_window_v1",
            chunker_version="1",
            version_no=1,
            is_current=True,
        )
        for index in range(3)
    ]
    db = SimpleNamespace(
        execute=lambda stmt: [
            SimpleNamespace(DocumentChunkModel=chunk, original_filename="irat.pdf")
            for chunk in chunks
        ]
    )

    retrieved = analysis_module_common.select_source_chunks(
        db,
        case_id,
        AnalysisModuleRunRequest(source_mode="document", document_id=document_id, query=None, max_chunks=50),
    )

    assert [item.label for item in retrieved] == ["chunk_1", "chunk_2", "chunk_3"]
    assert [item.chunk.chunk_index for item in retrieved] == [0, 1, 2]
    assert all(item.retrieval_score == 0.0 for item in retrieved)


def test_select_source_chunks_requires_document_id_for_document_mode() -> None:
    with pytest.raises(AnalysisModuleError):
        analysis_module_common.select_source_chunks(
            SimpleNamespace(),
            uuid4(),
            AnalysisModuleRunRequest(source_mode="document", query=None),
        )


def test_split_retrieved_chunks_and_batch_metadata_are_deterministic() -> None:
    chunks = [_retrieved_chunk(f"chunk_{index + 1}", f"A forras {index + 1}. allitasa.") for index in range(7)]

    batches = analysis_module_common.split_retrieved_chunks(chunks, batch_size=3)
    lookup = analysis_module_common.chunk_batch_lookup(batches)

    assert [len(batch) for batch in batches] == [3, 3, 1]
    assert lookup[chunks[0].chunk.id]["batch_index"] == 1
    assert lookup[chunks[3].chunk.id]["batch_index"] == 2
    assert lookup[chunks[6].chunk.id]["batch_index"] == 3
    assert lookup[chunks[6].chunk.id]["batch_count"] == 3
    assert lookup[chunks[0].chunk.id]["chunk_labels"] == ["chunk_1", "chunk_2", "chunk_3"]


def test_build_extract_claims_user_prompt_handles_empty_focus_and_batch_metadata() -> None:
    prompt = build_extract_claims_user_prompt(None, [_retrieved_chunk("chunk_1", "A forras allitasa.")], 2, 4)

    assert "Nincs kulon fokusz" in prompt
    assert "BATCH:\n2/4" in prompt
    assert "chunk_1:" in prompt


def test_build_extract_events_user_prompt_handles_empty_focus_and_batch_metadata() -> None:
    prompt = build_extract_events_user_prompt(None, [_retrieved_chunk("chunk_1", "18:42-kor hivas tortent.")], 3, 5)

    assert "Nincs kulon fokusz" in prompt
    assert "BATCH:\n3/5" in prompt
    assert "chunk_1:" in prompt
    assert "Az idezetek legyenek rovidek" in prompt
    assert "Keruld a dupla idezojelet" in prompt


def test_build_extract_entities_user_prompt_handles_empty_focus_and_batch_metadata() -> None:
    prompt = build_extract_entities_user_prompt(None, [_retrieved_chunk("chunk_1", "Kovacs Anna megjelent.")], 2, 3)

    assert "Nincs kulon fokusz" in prompt
    assert "BATCH:\n2/3" in prompt
    assert "chunk_1:" in prompt
    assert "Az idezetek legyenek rovidek" in prompt
    assert "Keruld a dupla idezojelet" in prompt


def test_build_summarize_case_user_prompt_handles_empty_focus_and_batch_metadata() -> None:
    prompt = build_summarize_case_user_prompt(None, [_retrieved_chunk("chunk_1", "A forras lenyeges allitast tartalmaz.")], 2, 6)

    assert "Nincs kulon fokusz" in prompt
    assert "BATCH:\n2/6" in prompt
    assert "chunk_1:" in prompt
    assert "Legfeljebb 3 summary_items" in prompt
    assert "csak azt foglalja ossze" in prompt
    assert "Keruld a dupla idezojelet" in prompt


def test_build_detect_missing_items_user_prompt_handles_empty_focus_and_batch_metadata() -> None:
    prompt = build_detect_missing_items_user_prompt(None, [_retrieved_chunk("chunk_1", "A 3. szamu melleklet hivatkozott.")], 2, 5)

    assert "Nincs kulon fokusz" in prompt
    assert "BATCH:\n2/5" in prompt
    assert "chunk_1:" in prompt
    assert "Ne allitsd, hogy az elem tenylegesen hianyzik" in prompt
    assert "Keruld a dupla idezojelet" in prompt


def test_build_detect_contradictions_user_prompt_handles_empty_focus() -> None:
    claims = [
        _retrieved_claim("claim_1", "A hivas 18:42-kor tortent."),
        _retrieved_claim("claim_2", "A hivas 19:10-kor tortent."),
    ]
    pairs = [ClaimPair(label="pair_1", claim_a=claims[0], claim_b=claims[1])]

    prompt = build_detect_contradictions_user_prompt(None, pairs, max_candidates=3)

    assert "Nincs kulon fokusz" in prompt
    assert "CLAIM_PAIRS" in prompt
    assert "pair_1:" in prompt
    assert "claim_label_a: claim_1" in prompt
    assert "claim_label_b: claim_2" in prompt
    assert "legfeljebb 3" in prompt
    assert "Ne allitsd, hogy az ellentmondas bizonyitott" in prompt
    assert "Keruld a dupla idezojelet" in prompt


def test_select_claim_pairs_is_deterministic_and_limits_pairs() -> None:
    claims = [
        _retrieved_claim("claim_1", "A hivas 18:42-kor tortent."),
        _retrieved_claim("claim_2", "A hivas 19:10-kor tortent."),
        _retrieved_claim("claim_3", "Dupin a helyszinen volt."),
        _retrieved_claim("claim_4", "A narrator jegyzetet keszitett."),
    ]

    selected_claims, pairs, metadata = select_claim_pairs_for_contradiction_detection(claims, None, max_pairs=2)

    assert [claim.label for claim in selected_claims] == ["claim_1", "claim_2", "claim_3"]
    assert [(pair.label, pair.claim_a.label, pair.claim_b.label) for pair in pairs] == [
        ("pair_1", "claim_1", "claim_2"),
        ("pair_2", "claim_1", "claim_3"),
    ]
    assert metadata["focus_filter_applied"] is False


def test_select_claim_pairs_applies_focus_filter_to_claim_and_quote_text() -> None:
    claims = [
        _retrieved_claim("claim_1", "A hivas 18:42-kor tortent."),
        _retrieved_claim("claim_2", "Dupin a helyszinen volt."),
        _retrieved_claim("claim_3", "A narrator Dupin mellett allt."),
    ]

    selected_claims, pairs, metadata = select_claim_pairs_for_contradiction_detection(
        claims,
        "narrátor Dupin",
        max_pairs=5,
    )

    assert [claim.label for claim in selected_claims] == ["claim_2", "claim_3"]
    assert [(pair.claim_a.label, pair.claim_b.label) for pair in pairs] == [("claim_2", "claim_3")]
    assert metadata["focus_filter_applied"] is True
    assert metadata["focus_terms"] == ["narrator", "dupin"]
    assert metadata["focus_matched_claim_count"] == 2


def test_select_claim_pairs_ignores_generic_contradiction_prompt_terms() -> None:
    claims = [
        _retrieved_claim("claim_1", "A hivas 18:42-kor tortent."),
        _retrieved_claim("claim_2", "A hivas 19:10-kor tortent."),
    ]

    selected_claims, pairs, metadata = select_claim_pairs_for_contradiction_detection(
        claims,
        "Keress ellentmondasokat.",
        max_pairs=5,
    )

    assert [claim.label for claim in selected_claims] == ["claim_1", "claim_2"]
    assert [(pair.claim_a.label, pair.claim_b.label) for pair in pairs] == [("claim_1", "claim_2")]
    assert metadata["focus_filter_applied"] is False
    assert metadata["focus_terms"] == []


def test_claim_review_statuses_for_scope_excludes_rejected_by_default() -> None:
    assert claim_review_statuses_for_scope("reviewable") == ("new", "needs_review", "verified", "corrected")
    assert claim_review_statuses_for_scope("verified") == ("verified",)
    assert claim_review_statuses_for_scope("needs_review") == ("needs_review",)
    assert claim_review_statuses_for_scope("unknown") == ("new", "needs_review", "verified", "corrected")


def test_detect_contradictions_returns_warning_when_not_enough_claims(monkeypatch) -> None:
    run = SimpleNamespace(id=uuid4(), status="running")
    inputs = []

    monkeypatch.setattr(analysis_module_contradictions, "start_analysis_run", lambda *args, **kwargs: run)
    monkeypatch.setattr(analysis_module_contradictions, "retrieve_claims_for_contradiction_detection", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        analysis_module_contradictions,
        "add_analysis_run_input",
        lambda db, run_id, input_type, sequence_no, **kwargs: inputs.append(
            {
                "input_type": input_type,
                "sequence_no": sequence_no,
                "payload_json": kwargs.get("payload_json"),
            }
        ),
    )

    def _finish_run(db, analysis_run, *, status, validation_status, output_summary=None, error_message=None):
        analysis_run.status = status
        analysis_run.validation_status = validation_status
        analysis_run.output_summary = output_summary

    monkeypatch.setattr(analysis_module_contradictions, "finish_analysis_run", _finish_run)

    response = analysis_module_contradictions.run_detect_contradiction_candidates(
        SimpleNamespace(),
        uuid4(),
        AnalysisModuleRunRequest(query="Keress ellentmondasokat.", limit=5),
    )

    assert response.validation_status == "warning"
    assert response.contradiction_candidates == []
    assert response.unsupported_items == [
        "Legalabb ket source-valid claim szukseges az ellentmondasjeloltek keresesehez."
    ]
    assert run.status == "succeeded"
    assert inputs[1]["input_type"] == "filter"
    assert inputs[1]["payload_json"]["input_kind"] == "claim_selection"
    assert inputs[1]["payload_json"]["retrieved_claim_count"] == 0
    assert inputs[1]["payload_json"]["selected_pairs"] == []
    assert inputs[1]["payload_json"]["claim_review_scope"] == "reviewable"
    assert "rejected" not in inputs[1]["payload_json"]["claim_review_statuses"]


def test_detect_contradictions_returns_warning_when_llm_json_is_invalid(monkeypatch) -> None:
    run = SimpleNamespace(id=uuid4(), status="running")
    claims = [
        _retrieved_claim("claim_1", "A hivas 18:42-kor tortent."),
        _retrieved_claim("claim_2", "A hivas 19:10-kor tortent."),
    ]

    class _FakeProvider:
        def __init__(self, settings):
            pass

        def chat_completion(self, *args, **kwargs):
            return SimpleNamespace(content="nem json")

    monkeypatch.setattr(analysis_module_contradictions, "start_analysis_run", lambda *args, **kwargs: run)
    monkeypatch.setattr(
        analysis_module_contradictions,
        "retrieve_claims_for_contradiction_detection",
        lambda *args, **kwargs: claims,
    )
    monkeypatch.setattr(analysis_module_contradictions, "add_analysis_run_input", lambda *args, **kwargs: None)
    monkeypatch.setattr(analysis_module_contradictions, "LMStudioNativeProvider", _FakeProvider)

    def _finish_run(db, analysis_run, *, status, validation_status, output_summary=None, error_message=None):
        analysis_run.status = status
        analysis_run.validation_status = validation_status
        analysis_run.output_summary = output_summary

    monkeypatch.setattr(analysis_module_contradictions, "finish_analysis_run", _finish_run)

    response = analysis_module_contradictions.run_detect_contradiction_candidates(
        SimpleNamespace(),
        uuid4(),
        AnalysisModuleRunRequest(query=None, limit=5),
    )

    assert response.validation_status == "warning"
    assert response.contradiction_candidates == []
    assert "nem volt ervenyes JSON" in response.unsupported_items[0]
    assert run.output_summary["llm_json_error"] == "LLM returned invalid JSON"


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


def test_validate_extracted_contradiction_candidates_requires_two_labeled_claims() -> None:
    claims = [
        _retrieved_claim("claim_1", "A hivas 18:42-kor tortent."),
        _retrieved_claim("claim_2", "A hivas 19:10-kor tortent."),
    ]
    payload = {
        "contradiction_candidates": [
            {
                "is_contradiction_candidate": True,
                "conflict_basis": "time",
                "contradiction_type": "time_conflict",
                "title": "Eltérő hívásidőpontok",
                "description": "A két claim eltérő időpontot ad meg ugyanarra a hívásra.",
                "claim_label_a": "claim_1",
                "claim_label_b": "claim_2",
                "severity_hint": "medium",
                "confidence": "low",
            }
        ],
        "unsupported_contradiction_candidates": [],
    }

    valid_candidates, unsupported = validate_extracted_contradiction_candidates(payload, claims)

    assert len(valid_candidates) == 1
    assert valid_candidates[0]["contradiction_type"] == "time_conflict"
    assert valid_candidates[0]["title"] == "Ellenorizendo idobeli elteres"
    assert "Ez ellenorizendo jelolt, nem bizonyitott ellentmondas." in valid_candidates[0]["description"]
    assert "A hivas 18:42-kor tortent." in valid_candidates[0]["description"]
    assert valid_candidates[0]["severity_hint"] == "medium"
    assert str(valid_candidates[0]["confidence"]) == "0.3000"
    assert unsupported == []


def test_validate_extracted_contradiction_candidates_rejects_self_reference_and_unknown_values() -> None:
    claims = [
        _retrieved_claim("claim_1", "A hivas 18:42-kor tortent."),
        _retrieved_claim("claim_2", "A hivas 19:10-kor tortent."),
    ]
    payload = {
        "contradiction_candidates": [
            {
                "is_contradiction_candidate": True,
                "conflict_basis": "mutually_exclusive_fact",
                "contradiction_type": "legal_conclusion",
                "title": "Onhivatkozas",
                "description": "Nem ervenyes par.",
                "claim_label_a": "claim_1",
                "claim_label_b": "claim_1",
                "severity_hint": "critical",
                "confidence": 2,
            },
            {
                "is_contradiction_candidate": True,
                "conflict_basis": "mutually_exclusive_fact",
                "contradiction_type": "legal_conclusion",
                "title": "Ismeretlen cimke",
                "description": "Nem letezo claim cimke.",
                "claim_label_a": "claim_1",
                "claim_label_b": "claim_99",
            },
        ],
        "unsupported_contradiction_candidates": ["nincs eleg par"],
    }

    valid_candidates, unsupported = validate_extracted_contradiction_candidates(payload, claims)

    assert valid_candidates == []
    assert unsupported == ["nincs eleg par"]


def test_validate_extracted_contradiction_candidates_rejects_pair_outside_selection() -> None:
    claims = [
        _retrieved_claim("claim_1", "A hivas 18:42-kor tortent."),
        _retrieved_claim("claim_2", "A hivas 19:10-kor tortent."),
        _retrieved_claim("claim_3", "A hivas 20:00-kor tortent."),
    ]
    allowed_pairs = [ClaimPair(label="pair_1", claim_a=claims[0], claim_b=claims[1])]
    payload = {
        "contradiction_candidates": [
            {
                "is_contradiction_candidate": True,
                "conflict_basis": "time",
                "contradiction_type": "time_conflict",
                "title": "Nem engedelyezett par",
                "description": "A modell nem a megadott parra hivatkozik.",
                "claim_label_a": "claim_1",
                "claim_label_b": "claim_3",
            }
        ],
        "unsupported_contradiction_candidates": [],
    }

    valid_candidates, unsupported = validate_extracted_contradiction_candidates(payload, claims, allowed_pairs)

    assert valid_candidates == []
    assert unsupported == []


def test_validate_extracted_contradiction_candidates_rejects_related_but_non_conflicting_pair() -> None:
    claims = [
        _retrieved_claim("claim_1", "Dupin megvizsgalta a helyszint."),
        _retrieved_claim("claim_2", "Dupin kesobb beszelgetett a narratorral."),
    ]
    payload = {
        "contradiction_candidates": [
            {
                "is_contradiction_candidate": False,
                "conflict_basis": "none",
                "contradiction_type": "other",
                "title": "Dupin tobb kontextusban szerepel",
                "description": "A ket claim osszefugg, de nem zarja ki egymast.",
                "claim_label_a": "claim_1",
                "claim_label_b": "claim_2",
            },
            {
                "conflict_basis": "none",
                "contradiction_type": "other",
                "title": "Hianyzo explicit dontes",
                "description": "Nincs explicit contradiction qualification.",
                "claim_label_a": "claim_1",
                "claim_label_b": "claim_2",
            },
        ],
        "unsupported_contradiction_candidates": ["pair_1: osszefuggo, de nincs konkretan utkozo teny"],
    }

    valid_candidates, unsupported = validate_extracted_contradiction_candidates(payload, claims)

    assert valid_candidates == []
    assert unsupported == ["pair_1: osszefuggo, de nincs konkretan utkozo teny"]


def test_validate_extracted_contradiction_candidates_deduplicates_pair_type_and_caps_high_severity() -> None:
    claims = [
        _retrieved_claim("claim_1", "A hivas 18:42-kor tortent."),
        _retrieved_claim("claim_2", "A hivas 19:10-kor tortent."),
    ]
    payload = {
        "contradiction_candidates": [
            {
                "is_contradiction_candidate": True,
                "conflict_basis": "time",
                "contradiction_type": "time_conflict",
                "title": "Eltérő hívásidőpont",
                "description": "Az egyik claim 18:42-t, a masik 19:10-et emlit.",
                "claim_label_a": "claim_1",
                "claim_label_b": "claim_2",
                "severity_hint": "high",
            },
            {
                "is_contradiction_candidate": True,
                "conflict_basis": "time",
                "contradiction_type": "time_conflict",
                "title": "Ugyanaz a hívásidő eltérés más címmel",
                "description": "Ugyanarra a claim parra ad uj jeloltet.",
                "claim_label_a": "claim_2",
                "claim_label_b": "claim_1",
                "severity_hint": "medium",
            },
        ],
        "unsupported_contradiction_candidates": [],
    }

    valid_candidates, unsupported = validate_extracted_contradiction_candidates(payload, claims)

    assert len(valid_candidates) == 1
    assert valid_candidates[0]["severity_hint"] == "medium"
    assert unsupported == []


def test_validate_extracted_contradiction_candidates_allows_high_for_document_mismatch() -> None:
    claims = [
        _retrieved_claim("claim_1", "Az irat 3 oldalt tartalmaz."),
        _retrieved_claim("claim_2", "Az irat 8 oldalt tartalmaz."),
    ]
    payload = {
        "contradiction_candidates": [
            {
                "is_contradiction_candidate": True,
                "conflict_basis": "document_metadata",
                "contradiction_type": "document_mismatch",
                "title": "Irat terjedelmi elteres",
                "description": "A claim par eltero oldalszamot emlit ugyanarra az iratra.",
                "claim_label_a": "claim_1",
                "claim_label_b": "claim_2",
                "severity_hint": "high",
            }
        ],
        "unsupported_contradiction_candidates": [],
    }

    valid_candidates, _unsupported = validate_extracted_contradiction_candidates(payload, claims)

    assert valid_candidates[0]["severity_hint"] == "high"


def test_validate_extracted_contradiction_candidates_replaces_overstated_model_description() -> None:
    claims = [
        _retrieved_claim("claim_1", "A forras szerint az irat 3 oldalas."),
        _retrieved_claim("claim_2", "A forras szerint az irat 8 oldalas."),
    ]
    payload = {
        "contradiction_candidates": [
            {
                "is_contradiction_candidate": True,
                "conflict_basis": "document_metadata",
                "contradiction_type": "document_mismatch",
                "title": "A modell szerint bizonyított súlyos irathiba",
                "description": "Ez bizonyított és súlyos logikai ellentmondást jelent.",
                "claim_label_a": "claim_1",
                "claim_label_b": "claim_2",
                "severity_hint": "high",
            }
        ],
        "unsupported_contradiction_candidates": [],
    }

    valid_candidates, _unsupported = validate_extracted_contradiction_candidates(payload, claims)

    assert valid_candidates[0]["title"] == "Ellenorizendo iratosszeferhetetlenseg"
    assert "bizonyított és súlyos" not in valid_candidates[0]["description"]
    assert "A forras szerint az irat 3 oldalas." in valid_candidates[0]["description"]
    assert "A forras szerint az irat 8 oldalas." in valid_candidates[0]["description"]


def test_validate_extracted_missing_item_candidates_requires_quote_in_labeled_chunk() -> None:
    chunks = [_retrieved_chunk("chunk_1", "Az irat szerint a 3. szamu melleklet tartalmazza a kamerafelvetelt.")]
    payload = {
        "missing_item_candidates": [
            {
                "missing_item_type": "attachment",
                "referenced_item_text": "3. szamu melleklet",
                "description": "A forras a 3. szamu mellekletre hivatkozik, amely kulon ellenorizendo.",
                "expected_document_type": "melleklet",
                "quote_text": "3. szamu melleklet tartalmazza a kamerafelvetelt",
                "source_label": "chunk_1",
                "confidence": "medium",
            }
        ],
        "unsupported_missing_item_candidates": [],
    }

    valid_candidates, unsupported = validate_extracted_missing_item_candidates(payload, chunks)

    assert len(valid_candidates) == 1
    assert valid_candidates[0]["missing_item_type"] == "attachment"
    assert str(valid_candidates[0]["confidence"]) == "0.6000"
    assert unsupported == []


def test_validate_extracted_missing_item_candidates_normalizes_unknown_values() -> None:
    chunks = [_retrieved_chunk("chunk_1", "A forras egy meg nem nevezett tovabbi dokumentumra hivatkozik.")]
    payload = {
        "missing_item_candidates": [
            {
                "missing_item_type": "verdict",
                "referenced_item_text": "tovabbi dokumentum",
                "description": "A forras tovabbi dokumentumra hivatkozik.",
                "expected_document_type": 42,
                "quote_text": "tovabbi dokumentumra hivatkozik",
                "source_label": "chunk_1",
                "confidence": 2,
            }
        ],
        "unsupported_missing_item_candidates": ["nincs megallapitas hianyrol"],
    }

    valid_candidates, unsupported = validate_extracted_missing_item_candidates(payload, chunks)

    assert valid_candidates[0]["missing_item_type"] == "other"
    assert valid_candidates[0]["expected_document_type"] is None
    assert valid_candidates[0]["confidence"] is None
    assert unsupported == ["nincs megallapitas hianyrol"]
