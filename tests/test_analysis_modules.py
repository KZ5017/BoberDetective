from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

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
from app.services.analysis_module_claims import build_extract_claims_user_prompt, parse_claims_json_lenient, parse_claims_json_with_repair
from app.services.analysis_modules import (
    AnalysisModuleError,
    RetrievedChunk,
    analysis_retrieval_queries,
    parse_llm_json_object,
    validate_extracted_claims,
    validate_extracted_contradiction_candidates,
    validate_extracted_entities,
    validate_extracted_events,
    validate_extracted_findings,
    validate_extracted_missing_item_candidates,
    validate_extracted_summary_items,
)
from app.services.analysis_module_events import _effective_event_batch_size, build_extract_events_user_prompt
from app.services.analysis_module_entities import build_extract_entities_user_prompt
from app.services.analysis_module_findings import build_search_findings_user_prompt
from app.services.analysis_module_summaries import build_summarize_case_user_prompt
from app.services.analysis_module_missing_items import build_detect_missing_items_user_prompt
from app.services.llm import LLMChatCompletion
from app.services.search import KeywordSearchHit


def test_analysis_module_request_rejects_legacy_limit_field() -> None:
    with pytest.raises(ValidationError):
        AnalysisModuleRunRequest(query="fokusz", limit=5)


def test_analysis_module_request_rejects_invalid_page_range() -> None:
    with pytest.raises(ValidationError):
        AnalysisModuleRunRequest(query="fokusz", page_start=12, page_end=8)


def test_analysis_module_request_rejects_page_range_in_case_mode() -> None:
    with pytest.raises(ValidationError):
        AnalysisModuleRunRequest(source_mode="case", query="fokusz", page_start=2, page_end=4)


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


def test_parse_claims_json_with_repair_recovers_unescaped_quote_text() -> None:
    class FakeRepairProvider:
        def chat_completion(self, model, messages, *, temperature=0.1, max_tokens=800):
            assert model == "chat-model"
            assert temperature == 0.0
            assert "HIBAS JSON-SZERU VALASZ" in messages[-1].content
            return LLMChatCompletion(
                model=model,
                content=(
                    '{"claims":[{"claim_type":"document_fact","claim_text":"Anyagi lenyek voltak.",'
                    '"quote_text":"\\"anyagi lenyek\\" voltak","source_label":"chunk_1"}],'
                    '"unsupported_claims":[]}'
                ),
            )

    payload = parse_claims_json_with_repair(
        '{"claims":[{"claim_type":"document_fact","claim_text":"Anyagi lenyek voltak.",'
        '"quote_text":""anyagi lenyek" voltak","source_label":"chunk_1"}],"unsupported_claims":[]}',
        FakeRepairProvider(),
        "chat-model",
    )

    assert payload["claims"][0]["quote_text"] == '"anyagi lenyek" voltak'


def test_parse_claims_json_lenient_recovers_quote_text_with_internal_comma_quote() -> None:
    raw_content = """
{
"claims": [
{
"claim_type": "document_fact",
"claim_text": "Dupin szerint a gyilkossag elkovetoje kulonos hangon beszelt.",
"quote_text": "a , kulonos, rikacsolo ( vagy erdes) hanggal", azzal az egyenetlenul hangzo beszedel,",
"source_label": "chunk_2"
}
],
"unsupported_claims": []
}
"""

    payload = parse_claims_json_lenient(raw_content)

    assert payload is not None
    assert payload["claims"][0]["quote_text"] == 'a , kulonos, rikacsolo ( vagy erdes) hanggal", azzal az egyenetlenul hangzo beszedel,'
    assert payload["claims"][0]["source_label"] == "chunk_2"


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


def test_analysis_retrieval_queries_keep_accents_and_two_letter_terms() -> None:
    queries = analysis_retrieval_queries("Keress úr nő narrátor ügy témáról.")

    assert "Keress úr nő narrátor ügy témáról." in queries
    assert "úr" in queries
    assert "nő" in queries
    assert "narrátor" in queries
    assert "ügy" in queries
    assert "téma" in queries


def test_retrieve_chunks_raises_when_focus_matches_no_source(monkeypatch) -> None:
    monkeypatch.setattr(analysis_module_common, "keyword_search", lambda *args, **kwargs: [])
    monkeypatch.setattr(analysis_module_common, "_effective_document_ids", lambda *args, **kwargs: [uuid4()])

    with pytest.raises(AnalysisModuleError, match="No source chunks matched"):
        analysis_module_common.retrieve_chunks(
            SimpleNamespace(),
            uuid4(),
            AnalysisModuleRunRequest(query="Keszits rovid ugyosszefoglalot.", max_chunks=5),
        )


def test_retrieve_chunks_requires_query() -> None:
    with pytest.raises(AnalysisModuleError):
        analysis_module_common.retrieve_chunks(
            SimpleNamespace(),
            uuid4(),
            AnalysisModuleRunRequest(source_mode="case", query=None),
        )


def test_select_source_chunks_requires_focus_text_for_document_mode() -> None:
    with pytest.raises(AnalysisModuleError, match="Focus text is required"):
        analysis_module_common.select_source_chunks(
            SimpleNamespace(),
            uuid4(),
            AnalysisModuleRunRequest(source_mode="document", document_id=uuid4(), query=None),
        )


def test_select_source_chunks_rejects_page_range_beyond_scope(monkeypatch) -> None:
    monkeypatch.setattr(analysis_module_common, "_source_scope_max_page", lambda *args, **kwargs: 30)
    monkeypatch.setattr(analysis_module_common, "_document_is_active", lambda *args, **kwargs: True)

    with pytest.raises(AnalysisModuleError, match="Page range"):
        analysis_module_common.select_source_chunks(
            SimpleNamespace(),
            uuid4(),
            AnalysisModuleRunRequest(source_mode="document", document_id=uuid4(), query="fokusz", page_start=20, page_end=50),
        )


def test_select_source_chunks_rejects_inactive_document(monkeypatch) -> None:
    monkeypatch.setattr(analysis_module_common, "_document_is_active", lambda *args, **kwargs: False)

    with pytest.raises(AnalysisModuleError, match="Selected document is not active"):
        analysis_module_common.select_source_chunks(
            SimpleNamespace(),
            uuid4(),
            AnalysisModuleRunRequest(source_mode="document", document_id=uuid4(), query="fokusz"),
        )


def test_select_source_chunks_document_mode_defaults_to_full_document_range(monkeypatch) -> None:
    case_id = uuid4()
    document_id = uuid4()
    captured_ranges = []

    def fake_retrieve_source_scope_chunks(db, case_id_arg, payload, *, document_id=None, page_start=None, page_end=None):
        captured_ranges.append((document_id, page_start, page_end))
        return [_retrieved_chunk("chunk_1", "A teljes iratbol valasztott forras.")]

    monkeypatch.setattr(analysis_module_common, "_source_scope_max_page", lambda *args, **kwargs: 42)
    monkeypatch.setattr(analysis_module_common, "_document_is_active", lambda *args, **kwargs: True)
    monkeypatch.setattr(analysis_module_common, "retrieve_source_scope_chunks", fake_retrieve_source_scope_chunks)

    retrieved = analysis_module_common.select_source_chunks(
        SimpleNamespace(),
        case_id,
        AnalysisModuleRunRequest(source_mode="document", document_id=document_id, query="fokusz"),
    )

    assert len(retrieved) == 1
    assert captured_ranges == [(document_id, 1, 42)]


def test_select_source_chunks_case_mode_passes_document_ids(monkeypatch) -> None:
    document_ids = [uuid4(), uuid4()]
    captured_document_ids = []

    def fake_retrieve_source_scope_chunks(
        db,
        case_id_arg,
        payload,
        *,
        document_id=None,
        document_ids=None,
        page_start=None,
        page_end=None,
    ):
        captured_document_ids.extend(document_ids or [])
        return [_retrieved_chunk("chunk_1", "Tobb iratbol szurt forras.")]

    monkeypatch.setattr(analysis_module_common, "retrieve_source_scope_chunks", fake_retrieve_source_scope_chunks)

    retrieved = analysis_module_common.select_source_chunks(
        SimpleNamespace(),
        uuid4(),
        AnalysisModuleRunRequest(source_mode="case", query="fokusz", document_ids=document_ids),
    )

    assert len(retrieved) == 1
    assert captured_document_ids == document_ids


def test_analysis_request_rejects_taxonomy_filters_in_document_mode() -> None:
    with pytest.raises(ValidationError):
        AnalysisModuleRunRequest(
            source_mode="document",
            document_id=uuid4(),
            query="fokusz",
            document_group_code="procedural_records",
        )


def test_analysis_request_rejects_document_type_without_group() -> None:
    with pytest.raises(ValidationError):
        AnalysisModuleRunRequest(source_mode="case", query="fokusz", document_type_code="jegyzokonyv")


def test_select_source_chunks_uses_retrieval_for_document_mode_with_focus(monkeypatch) -> None:
    case_id = uuid4()
    document_id = uuid4()
    chunk = DocumentChunkModel(
        id=uuid4(),
        case_id=case_id,
        document_id=document_id,
        page_start=3,
        page_end=3,
        chunk_index=2,
        chunk_text="A keresett esemeny itt szerepel.",
        char_start=0,
        char_end=32,
        token_count=6,
        chunking_strategy="char_window_v1",
        chunker_version="1",
        version_no=1,
        is_current=True,
    )
    captured_document_ids = []
    captured_page_ranges = []

    def fake_keyword_search(db, case_id_arg, request):
        captured_document_ids.extend(request.filters.document_ids)
        captured_page_ranges.append((request.filters.page_start, request.filters.page_end))
        return [
            KeywordSearchHit(
                source_type="chunk",
                document_id=document_id,
                document_name="irat.pdf",
                page_start=3,
                page_end=3,
                score=0.7,
                chunk_id=chunk.id,
                chunk_index=2,
            )
        ]

    db = SimpleNamespace(get=lambda model, item_id: chunk if item_id == chunk.id else None)
    monkeypatch.setattr(analysis_module_common, "keyword_search", fake_keyword_search)
    monkeypatch.setattr(analysis_module_common, "_source_scope_max_page", lambda *args, **kwargs: 10)
    monkeypatch.setattr(analysis_module_common, "_document_is_active", lambda *args, **kwargs: True)
    monkeypatch.setattr(analysis_module_common, "_effective_document_ids", lambda *args, **kwargs: [document_id])

    retrieved = analysis_module_common.select_source_chunks(
        db,
        case_id,
        AnalysisModuleRunRequest(
            source_mode="document",
            document_id=document_id,
            query="keresett esemeny",
            page_start=2,
            page_end=4,
            max_chunks=10,
        ),
    )

    assert captured_document_ids
    assert set(captured_document_ids) == {document_id}
    assert captured_page_ranges
    assert set(captured_page_ranges) == {(2, 4)}
    assert len(retrieved) == 1
    assert retrieved[0].chunk == chunk
    assert retrieved[0].match_type == "keyword"
    assert retrieved[0].retrieval_score == 0.7


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

    assert "Nincs külön fókusz" in prompt
    assert "BATCH:\n2/4" in prompt
    assert "chunk_1:" in prompt


def test_build_extract_events_user_prompt_handles_empty_focus_and_batch_metadata() -> None:
    prompt = build_extract_events_user_prompt(None, [_retrieved_chunk("chunk_1", "18:42-kor hivas tortent.")], 3, 5)

    assert "Nincs külön fókusz" in prompt
    assert "BATCH:\n3/5" in prompt
    assert "chunk_1:" in prompt
    assert "quote_text ne legyen túl szűk" in prompt
    assert "Kerüld a dupla idézőjelet" in prompt


def test_extract_events_caps_effective_batch_size_for_local_llm_stability() -> None:
    assert _effective_event_batch_size(10) == 2
    assert _effective_event_batch_size(5) == 2
    assert _effective_event_batch_size(1) == 1


def test_build_extract_entities_user_prompt_handles_empty_focus_and_batch_metadata() -> None:
    prompt = build_extract_entities_user_prompt(None, [_retrieved_chunk("chunk_1", "Kovacs Anna megjelent.")], 2, 3)

    assert "Nincs külön fókusz" in prompt
    assert "BATCH:\n2/3" in prompt
    assert "chunk_1:" in prompt
    assert "quote_text ne legyen túl szűk" in prompt
    assert "Kerüld a dupla idézőjelet" in prompt


def test_build_search_findings_user_prompt_is_source_bound_and_type_flexible() -> None:
    prompt = build_search_findings_user_prompt(
        "matrózzal kapcsolatos releváns találatok",
        [_retrieved_chunk("chunk_1", "A matróz benézett az ablakon.")],
        1,
        2,
    )

    assert "QUERY:\nmatrózzal kapcsolatos releváns találatok" in prompt
    assert "BATCH:\n1/2" in prompt
    assert "chunk_1:" in prompt
    assert "Ne erőltesd, hogy a találat állítás, esemény vagy entitás legyen" in prompt
    assert "suggested_type" in prompt


def test_validate_extracted_findings_accepts_exact_source_quote_and_normalizes_unknown_type() -> None:
    chunks = [_retrieved_chunk("chunk_1", "A matróz benézett az ablakon, majd megijedt.")]

    findings, unsupported = validate_extracted_findings(
        {
            "findings": [
                {
                    "title": "Matróz az ablaknál",
                    "finding_text": "A matróz benézett az ablakon.",
                    "suggested_type": "scene",
                    "suggested_type_reason": "Inkább eseményszerű, de nem biztos.",
                    "relevance_reason": "A fókusz a matróz cselekményeire irányult.",
                    "quote_text": "A matróz benézett az ablakon",
                    "source_label": "chunk_1",
                }
            ],
            "unsupported_findings": ["nincs elég forrás"],
        },
        chunks,
    )

    assert len(findings) == 1
    assert findings[0]["suggested_type"] == "other"
    assert unsupported == ["nincs elég forrás"]


def test_validate_extracted_findings_skips_quote_outside_source_chunk() -> None:
    chunks = [_retrieved_chunk("chunk_1", "A forrásban ez a mondat szerepel.")]

    findings, unsupported = validate_extracted_findings(
        {
            "findings": [
                {
                    "title": "Nem forráshű találat",
                    "finding_text": "Olyasmi, ami nincs a forrásban.",
                    "suggested_type": "claim",
                    "relevance_reason": "A fókuszhoz kapcsolódna.",
                    "quote_text": "Ez nincs a chunkban.",
                    "source_label": "chunk_1",
                }
            ],
            "unsupported_findings": [],
        },
        chunks,
    )

    assert findings == []
    assert unsupported == []


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
        _retrieved_claim("claim_3", "A narrátor Dupin mellett allt."),
    ]

    selected_claims, pairs, metadata = select_claim_pairs_for_contradiction_detection(
        claims,
        "narrátor Dupin",
        max_pairs=5,
    )

    assert [claim.label for claim in selected_claims] == ["claim_2", "claim_3"]
    assert [(pair.claim_a.label, pair.claim_b.label) for pair in pairs] == [("claim_2", "claim_3")]
    assert metadata["focus_filter_applied"] is True
    assert metadata["focus_terms"] == ["narrátor", "dupin"]
    assert metadata["focus_matched_claim_count"] == 2


def test_claim_focus_terms_keep_accents_and_allow_two_letter_terms() -> None:
    terms = analysis_module_contradictions._claim_focus_terms("úr nő Dupin")

    assert terms == ["úr", "nő", "dupin"]


def test_detect_contradictions_requires_focus_text() -> None:
    with pytest.raises(AnalysisModuleError, match="Focus text is required"):
        analysis_module_contradictions.run_detect_contradiction_candidates(
            SimpleNamespace(),
            uuid4(),
            AnalysisModuleRunRequest(query=None),
        )


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
        AnalysisModuleRunRequest(query="Keress ellentmondasokat.", contradiction_candidate_limit=5),
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
        AnalysisModuleRunRequest(query="hivas idopont", contradiction_candidate_limit=5),
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
