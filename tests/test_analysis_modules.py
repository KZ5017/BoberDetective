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
    EXTRACT_CONTRADICTIONS_SYSTEM_PROMPT,
    RetrievedClaim,
    build_detect_contradiction_candidates_user_prompt,
    claim_review_statuses_for_scope,
    select_claim_pairs_for_contradiction_detection,
)
from app.services.analysis_modules import (
    AnalysisModuleError,
    RetrievedChunk,
    analysis_retrieval_queries,
    parse_llm_json_object,
    run_analysis_module,
    validate_extracted_contradiction_candidates,
    validate_extracted_findings,
)
from app.services.analysis_module_findings import (
    SEARCH_FINDINGS_SYSTEM_PROMPT,
    build_search_findings_user_prompt,
    parse_search_findings_llm_json_object,
)
from app.services.search import KeywordSearchHit


def test_analysis_module_request_rejects_legacy_limit_field() -> None:
    with pytest.raises(ValidationError):
        AnalysisModuleRunRequest(query="fokusz", limit=5)


def test_analysis_module_request_uses_updated_chunk_cap_defaults() -> None:
    request = AnalysisModuleRunRequest(query="fokusz")

    assert request.max_chunks == 30
    assert request.batch_size == 3
    assert AnalysisModuleRunRequest(query="fokusz", max_chunks=60).max_chunks == 60
    with pytest.raises(ValidationError):
        AnalysisModuleRunRequest(query="fokusz", max_chunks=61)


@pytest.mark.parametrize(
    "module_key",
    ["extract_claims", "extract_events", "extract_entities", "summarize_case", "detect_missing_items"],
)
def test_retired_raw_chunk_module_keys_are_rejected(module_key: str) -> None:
    with pytest.raises(AnalysisModuleError, match="Unsupported analysis module"):
        run_analysis_module(None, uuid4(), module_key, AnalysisModuleRunRequest(query="fokusz"))  # type: ignore[arg-type]


def test_analysis_module_request_rejects_invalid_page_range() -> None:
    with pytest.raises(ValidationError):
        AnalysisModuleRunRequest(query="fokusz", page_start=12, page_end=8)


def test_analysis_module_request_rejects_page_range_in_case_mode() -> None:
    with pytest.raises(ValidationError):
        AnalysisModuleRunRequest(source_mode="case", query="fokusz", page_start=2, page_end=4)


def _retrieved_chunk(
    label: str,
    text: str,
    *,
    document_id=None,
    document_name: str = "irat.txt",
    page_start: int = 1,
    chunk_index: int = 0,
) -> RetrievedChunk:
    chunk = DocumentChunkModel(
        id=uuid4(),
        case_id=uuid4(),
        document_id=document_id or uuid4(),
        page_start=page_start,
        page_end=page_start,
        chunk_index=chunk_index,
        char_start=0,
        char_end=len(text),
        token_count=10,
        chunking_strategy="char_window_v1",
        chunker_version="1",
        version_no=1,
        is_current=True,
    )
    chunk._text_store_text = text
    return RetrievedChunk(
        label=label,
        document_name=document_name,
        chunk=chunk,
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
            claim_title=text,
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


def test_parse_search_findings_llm_json_object_recovers_unescaped_quote_in_quote_text() -> None:
    raw = (
        '{"findings":[{"source_label":"chunk_40",'
        '"quote_text":"Madame LEspanaye és leánya, Mademoiselle Camilla L"Espanaye lakik.",'
        '"title":"A Morgue utcában történt kettős gyilkosság első jelentése",'
        '"finding_text":"A szöveg az áldozatok lakóhelyét írja le.",'
        '"relevance_reason":"A quote_text megnevezi az áldozatokat.",'
        '"suggested_type":"event",'
        '"suggested_type_reason":"Egy konkrét esemény leírása."}]}'
    )

    payload = parse_search_findings_llm_json_object(raw)

    assert payload["findings"][0]["source_label"] == "chunk_40"
    assert payload["findings"][0]["quote_text"] == 'Madame LEspanaye és leánya, Mademoiselle Camilla L"Espanaye lakik.'
    assert payload["findings"][0]["suggested_type"] == "event"


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
    queries = analysis_retrieval_queries("Keress úr nő narrátor per témáról.")

    assert "Keress úr nő narrátor per témáról." in queries
    assert "úr" in queries
    assert "nő" in queries
    assert "narrátor" in queries
    assert "per" in queries
    assert "téma" in queries


def test_analysis_retrieval_queries_drop_hungarian_function_words_but_keep_original_query() -> None:
    queries = analysis_retrieval_queries("A tanú és a matróz vallomása.")

    assert queries[0] == "A tanú és a matróz vallomása."
    assert "tanú matróz vallomása" in queries
    assert "a" not in queries[1:]
    assert "és" not in queries[1:]


def test_retrieve_chunks_raises_when_focus_matches_no_source(monkeypatch) -> None:
    monkeypatch.setattr(analysis_module_common, "keyword_search", lambda *args, **kwargs: [])
    monkeypatch.setattr(analysis_module_common, "_effective_document_ids", lambda *args, **kwargs: [uuid4()])

    with pytest.raises(AnalysisModuleError, match="No source chunks matched"):
        analysis_module_common.retrieve_chunks(
            SimpleNamespace(),
            uuid4(),
            AnalysisModuleRunRequest(query="Keszits rovid ugyosszefoglalot.", max_chunks=5),
        )


def test_hybrid_retrieval_does_not_starve_keyword_variants(monkeypatch) -> None:
    case_id = uuid4()
    semantic_chunk = DocumentChunkModel(
        id=uuid4(),
        case_id=case_id,
        document_id=uuid4(),
        page_start=1,
        page_end=1,
        chunk_index=0,
        char_start=0,
        char_end=36,
        token_count=6,
        chunking_strategy="char_window_v1",
        chunker_version="1",
        version_no=1,
        is_current=True,
    )
    keyword_chunk = DocumentChunkModel(
        id=uuid4(),
        case_id=case_id,
        document_id=uuid4(),
        page_start=2,
        page_end=2,
        chunk_index=1,
        char_start=0,
        char_end=54,
        token_count=7,
        chunking_strategy="char_window_v1",
        chunker_version="1",
        version_no=1,
        is_current=True,
    )
    semantic_chunk._text_store_text = "Szemantikus, de nem konkret talalat."
    keyword_chunk._text_store_text = "Dupin a rendorseggel kapcsolatos megallapitast tesz."
    chunks = {semantic_chunk.id: semantic_chunk, keyword_chunk.id: keyword_chunk}

    def fake_keyword_search(db, case_id_arg, request):
        if request.query == "dupin rendorseg":
            return [
                KeywordSearchHit(
                    source_type="chunk",
                    document_id=keyword_chunk.document_id,
                    document_name="irat.pdf",
                    page_start=2,
                    page_end=2,
                    score=0.4,
                    chunk_id=keyword_chunk.id,
                    chunk_index=1,
                )
            ]
        return []

    def fake_hybrid_search(db, case_id_arg, query, keyword_hits, limit, **kwargs):
        if keyword_hits:
            return keyword_hits
        return [
            KeywordSearchHit(
                source_type="chunk",
                document_id=semantic_chunk.document_id,
                document_name="irat.pdf",
                page_start=1,
                page_end=1,
                score=0.9,
                chunk_id=semantic_chunk.id,
                chunk_index=0,
                match_type="semantic",
            )
        ]

    db = SimpleNamespace(get=lambda model, item_id: chunks.get(item_id))
    monkeypatch.setattr(analysis_module_common, "analysis_retrieval_queries", lambda query: [query, "dupin rendorseg"])
    monkeypatch.setattr(analysis_module_common, "keyword_search", fake_keyword_search)
    monkeypatch.setattr(analysis_module_common, "hybrid_chunk_search", fake_hybrid_search)
    monkeypatch.setattr(analysis_module_common, "_effective_document_ids", lambda *args, **kwargs: [keyword_chunk.document_id])

    retrieved = analysis_module_common._retrieve_chunks_by_query(  # noqa: SLF001
        db,
        case_id,
        "dupin velemenye a rendorsegrol",
        1,
        "hybrid",
    )

    assert [item.chunk.id for item in retrieved] == [keyword_chunk.id]


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


def test_analysis_module_request_requires_collection_id_for_collection_scope() -> None:
    with pytest.raises(ValidationError):
        AnalysisModuleRunRequest(source_mode="collection", query="fokusz")


def test_select_source_chunks_collection_mode_resolves_document_ids(monkeypatch) -> None:
    collection_id = uuid4()
    resolved_document_ids = [uuid4(), uuid4()]
    captured_document_ids = []

    def fake_resolve_document_scope(db, case_id, source_mode, *, collection_ids=None, document_ids=None):
        assert source_mode == "collections"
        assert collection_ids == [collection_id]
        return SimpleNamespace(resolved_document_ids=resolved_document_ids)

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
        return [_retrieved_chunk("chunk_1", "Gyujtemenybol szurt forras.")]

    monkeypatch.setattr(analysis_module_common, "resolve_document_scope", fake_resolve_document_scope)
    monkeypatch.setattr(analysis_module_common, "retrieve_source_scope_chunks", fake_retrieve_source_scope_chunks)

    retrieved = analysis_module_common.select_source_chunks(
        SimpleNamespace(),
        uuid4(),
        AnalysisModuleRunRequest(source_mode="collection", collection_id=collection_id, query="fokusz"),
    )

    assert len(retrieved) == 1
    assert captured_document_ids == resolved_document_ids


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
        char_start=0,
        char_end=32,
        token_count=6,
        chunking_strategy="char_window_v1",
        chunker_version="1",
        version_no=1,
        is_current=True,
    )
    chunk._text_store_text = "A keresett esemeny itt szerepel."
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
    document_id = uuid4()
    chunks = [
        _retrieved_chunk(
            f"chunk_{index + 1}",
            f"A forras {index + 1}. allitasa.",
            document_id=document_id,
            page_start=1,
            chunk_index=index,
        )
        for index in range(7)
    ]

    batches = analysis_module_common.split_retrieved_chunks(chunks, batch_size=3)
    lookup = analysis_module_common.chunk_batch_lookup(batches)

    assert [len(batch) for batch in batches] == [3, 3, 1]
    assert lookup[chunks[0].chunk.id]["batch_index"] == 1
    assert lookup[chunks[3].chunk.id]["batch_index"] == 2
    assert lookup[chunks[6].chunk.id]["batch_index"] == 3
    assert lookup[chunks[6].chunk.id]["batch_count"] == 3
    assert lookup[chunks[0].chunk.id]["chunk_labels"] == ["chunk_1", "chunk_2", "chunk_3"]


def test_split_retrieved_chunks_orders_sources_and_keeps_documents_separate() -> None:
    first_document_id = uuid4()
    second_document_id = uuid4()
    chunks = [
        _retrieved_chunk(
            "chunk_1",
            "Második irat első szövegrésze.",
            document_id=second_document_id,
            document_name="B_irata.txt",
            page_start=1,
            chunk_index=0,
        ),
        _retrieved_chunk(
            "chunk_2",
            "Első irat második szövegrésze.",
            document_id=first_document_id,
            document_name="A_irata.txt",
            page_start=2,
            chunk_index=1,
        ),
        _retrieved_chunk(
            "chunk_3",
            "Első irat első szövegrésze.",
            document_id=first_document_id,
            document_name="A_irata.txt",
            page_start=1,
            chunk_index=0,
        ),
    ]

    batches = analysis_module_common.split_retrieved_chunks(chunks, batch_size=3)

    assert [[retrieved.label for retrieved in batch] for batch in batches] == [["chunk_3", "chunk_2"], ["chunk_1"]]
    assert all(len({retrieved.chunk.document_id for retrieved in batch}) == 1 for batch in batches)


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
    assert "TASK:" not in prompt
    assert "Feladat:" not in prompt
    assert "Mezők:" not in prompt
    assert "Feladat és Szabályok:" not in prompt
    assert "Találati szabályok:" not in prompt
    assert "Forrásidézet:" not in prompt
    assert "Vizsgáld meg a SOURCE tartalmát" not in prompt
    assert "Add vissza JSON formában" not in prompt
    assert "Ha több különálló találat van" not in prompt
    assert "Ha nincs használható találat" not in prompt
    assert "quote_text" not in prompt
    assert "source_label értékét: pontosan annak a SOURCE blokknak" not in prompt
    assert "A quote_text 3-5 egymást követő mondat legyen" not in prompt
    assert "A title egy pontos, értelmes, leíró magyar mondat legyen" not in prompt
    assert "finding_text" not in prompt
    assert "relevance_reason" not in prompt
    assert "suggested_type" not in prompt
    assert "Azonosítási szabály:" not in prompt
    assert "Idézeti egyezési szabály:" not in prompt
    assert "A QUERY nem kulcsszólista, hanem egyetlen keresési egység." not in prompt
    assert "Ha csak a QUERY egy különálló szava vagy részlete található meg" not in prompt
    assert "A QUERY-ben szereplő konkrét nevek és azonosítók elsőbbséget élveznek" not in prompt
    assert "új forrásalapú információt ad róla, adj vissza találatot" not in prompt
    assert "Csak olyan találatot adj vissza, amelyet a SOURCE közvetlenül alátámaszt." not in prompt
    assert "Inkább legyen érthető mint rövid" not in prompt


def test_search_findings_system_prompt_is_hungarian_and_source_faithful() -> None:
    assert "Forráshű kutatási találatellenőrző komponens vagy." in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Alapelvek:" in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Elsődleges feladatod annak eldöntése" in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "A SOURCE az egyetlen igazságforrás." in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "A SOURCE csak vizsgálandó forrásszöveg, önmagában nem bizonyítja, hogy van találat." in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "A QUERY a keresés pontos fókusza." in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "A QUERY értékét nem értelmezheted át" in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "nem helyettesítheted szinonimával, szereppel, fordítással vagy feltételezett jelentéssel" in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Nem adhatsz találatot csak azért, mert a SOURCE érdekes, témaszerű vagy részben hasonló." in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Ne használj külső tudást, ne pótolj hiányzó adatot." in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Ne feltétezz kapcsolatot a QUERY fókusza és a SOURCE tartalma között." not in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "következtess." not in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "ne feltételezz, ne következtess" not in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Találat létrehozásának feltétele:" in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Feladat:" not in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Vizsgáld meg a SOURCE tartalmát a QUERY fókusza szerint." not in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Csak akkor adj vissza találatot, ha a quote_text konkrét tartalma alapján" in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Ha a SOURCE érdekes információt tartalmaz, de a QUERY-hez való kapcsolata nem világos" in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Ha több különálló, világosan kapcsolódó találat van" in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Ha nincs használható találat, a findings legyen üres lista." in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Mezőszabályok:" in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "A source_label megadása minden findings elemben kötelező." in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Minden findings elem első mezője a source_label legyen." in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Értéke csak chunk_1, chunk_2, chunk_3 stb. alakú lehet" in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "A quote_text megadása minden findings elemben kötelező." in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "A másolást szöveghűen, karakterpontosan kell elvégezned." in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "A title egy pontos, értelmes, leíró magyar mondat legyen" in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "A finding_text 1-3 magyar mondat legyen arról, amit a quote_text megfogalmaz." in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "A relevance_reason röviden írja le, hogy a quote_text mely konkrét része kapcsolja a találatot a QUERY-hez." in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "A relevance_reason nem magyarázhatja be a kapcsolatot." in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Ha nem, akkor other." in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Legalább 2, maximum 4 egymás után következő mondat legyen." not in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Nem alkalmazhatsz rövidítést és nem hagyhatsz ki forrásrészeket." not in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Ne fűzz össze egymástól különálló forrásrészleteket" not in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "JSON szabályok:" in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Csak érvényes JSON objektumot adhatsz vissza." in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Ne írj magyarázatot, markdown blokkot vagy JSON-on kívüli szöveget." in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert 'A JSON objektumok minden mezőneve dupla idézőjelben legyen, például "source_label", nem source_label.' in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "A JSON stringeken belüli dupla idézőjeleket escape-eld." in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Elvárt JSON forma:" in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert '{"findings":[{"source_label":"chunk_1","quote_text":"..."' in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "Ha nincs használható találat:" in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert '{"findings":[]}' in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "strict selection filter" not in SEARCH_FINDINGS_SYSTEM_PROMPT
    assert "not a keyword list" not in SEARCH_FINDINGS_SYSTEM_PROMPT


def test_validate_extracted_findings_accepts_exact_source_quote_and_normalizes_unknown_type() -> None:
    chunks = [_retrieved_chunk("chunk_1", "A matróz benézett az ablakon, majd megijedt.")]

    findings, unsupported, unconfirmed = validate_extracted_findings(
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
        },
        chunks,
    )

    assert len(findings) == 1
    assert findings[0]["suggested_type"] == "other"
    assert findings[0]["llm_support_status"] == "confirmed"
    assert findings[0]["source_validation_status"] == "source_valid"
    assert unsupported == []
    assert unconfirmed == []


def test_validate_extracted_findings_accepts_ocr_spacing_variant() -> None:
    chunks = [
        _retrieved_chunk(
            "chunk_1",
            "Néhány szót Kovács Ágnesr ő l. Kovács Ágnes három héttel ezel ő tt még manöken volt.",
        )
    ]

    findings, unsupported, unconfirmed = validate_extracted_findings(
        {
            "findings": [
                {
                    "title": "Kovács Ágnes korábbi munkája",
                    "finding_text": "Kovács Ágnes három héttel ezelőtt még manöken volt.",
                    "suggested_type": "entity",
                    "relevance_reason": "A találat Kovács Ágneshez kapcsolódó forrásbeli adatot ad.",
                    "quote_text": "Kovács Ágnes három héttel ezelőtt még manöken volt",
                    "source_label": "chunk_1",
                }
            ],
        },
        chunks,
    )

    assert len(findings) == 1
    assert findings[0]["quote_text"] == "Kovács Ágnes három héttel ezel ő tt még manöken volt"
    assert unsupported == []
    assert unconfirmed == []


def test_validate_extracted_findings_preserves_exact_quote_with_literal_ellipsis() -> None:
    source_text = "Kovács várt... aztán belépett a szobába. Ágnes az ablaknál állt."
    chunks = [_retrieved_chunk("chunk_1", source_text)]

    findings, unsupported, unconfirmed = validate_extracted_findings(
        {
            "findings": [
                {
                    "title": "Kovács belépett a szobába",
                    "finding_text": "Kovács várakozás után belépett a szobába.",
                    "suggested_type": "event",
                    "relevance_reason": "A találat Kovács cselekvéséhez kapcsolódik.",
                    "quote_text": source_text,
                    "source_label": "chunk_1",
                }
            ],
        },
        chunks,
    )

    assert len(findings) == 1
    assert findings[0]["quote_text"] == source_text
    assert findings[0]["llm_support_status"] == "confirmed"
    assert findings[0]["source_validation_status"] == "source_valid"
    assert unsupported == []
    assert unconfirmed == []


def test_validate_extracted_findings_repairs_partial_quote_match_as_source_valid() -> None:
    chunks = [
        _retrieved_chunk(
            "chunk_1",
            "Legalább Kovács itt volna! A beteg nyugtalanul járkált. "
            "A legokosabb lesz, ha mégiscsak elmegy Kováccsal a Hungáriába, és az esti vonattal elutazik. "
            "Segítség! Kovács úr!",
        )
    ]

    findings, unsupported, unconfirmed = validate_extracted_findings(
        {
            "findings": [
                {
                    "title": "Kovács keresése",
                    "finding_text": "A forrás több helyen Kovács jelenlétére vagy segítségére utal.",
                    "suggested_type": "claim",
                    "relevance_reason": "A fókusz Kovácsra irányul.",
                    "quote_text": "Legalább Kovács itt volna! ... A legokosabb lesz, ha mégiscsak elmegy Kováccsal a Hungáriába, és az esti vonattal elutazik. ... Segítség! Kovács úr!",
                    "source_label": "chunk_1",
                }
            ],
        },
        chunks,
    )

    assert len(findings) == 1
    assert findings[0]["llm_support_status"] == "unconfirmed"
    assert findings[0]["source_validation_status"] == "source_valid"
    assert findings[0]["quote_text"] == "A legokosabb lesz, ha mégiscsak elmegy Kováccsal a Hungáriába, és az esti vonattal elutazik."
    assert unsupported == []
    assert unconfirmed == []


def test_validate_extracted_findings_repairs_two_meaningful_short_partial_quote_matches_as_source_valid() -> None:
    chunks = [
        _retrieved_chunk(
            "chunk_1",
            "Kovács úr a folyosón állt. A nővér becsukta az ajtót. Kovács visszament a szobába.",
        )
    ]

    findings, unsupported, unconfirmed = validate_extracted_findings(
        {
            "findings": [
                {
                    "title": "Kovács két jelenléte",
                    "finding_text": "A forrás két külön mondatban is Kovács jelenlétére utal.",
                    "suggested_type": "entity",
                    "relevance_reason": "A találat Kovács szerepléséhez kapcsolódik.",
                    "quote_text": "Kovács úr a folyosón állt. ... Kovács visszament a szobába.",
                    "source_label": "chunk_1",
                }
            ],
        },
        chunks,
    )

    assert len(findings) == 1
    assert findings[0]["llm_support_status"] == "unconfirmed"
    assert findings[0]["source_validation_status"] == "source_valid"
    assert findings[0]["quote_text"] == "Kovács visszament a szobába."
    assert unsupported == []
    assert unconfirmed == []


def test_validate_extracted_findings_keeps_unrepairable_quote_as_source_invalid() -> None:
    chunks = [_retrieved_chunk("chunk_1", "Kovács úr itt volt. A nővér becsukta az ajtót.")]

    findings, unsupported, unconfirmed = validate_extracted_findings(
        {
            "findings": [
                {
                    "title": "Túl rövid részlet",
                    "finding_text": "A javasolt idézetnek csak egy rövid része található meg.",
                    "suggested_type": "entity",
                    "relevance_reason": "A találat Kovácshoz kapcsolódna.",
                    "quote_text": "Kovács úr itt volt. ... Ez a hosszabb rész nincs a forrásban.",
                    "source_label": "chunk_1",
                }
            ],
        },
        chunks,
    )

    assert len(findings) == 1
    assert findings[0]["llm_support_status"] == "unconfirmed"
    assert findings[0]["source_validation_status"] == "source_invalid"
    assert findings[0]["quote_text"] == "Kovács úr itt volt. ... Ez a hosszabb rész nincs a forrásban."
    assert unsupported == []
    assert unconfirmed == []


def test_validate_extracted_findings_keeps_quote_without_partial_match_as_source_invalid() -> None:
    chunks = [_retrieved_chunk("chunk_1", "A forrásban ez a mondat szerepel.")]

    findings, unsupported, unconfirmed = validate_extracted_findings(
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
        },
        chunks,
    )

    assert len(findings) == 1
    assert findings[0]["llm_support_status"] == "unconfirmed"
    assert findings[0]["source_validation_status"] == "source_invalid"
    assert findings[0]["quote_text"] == "Ez nincs a chunkban."
    assert unsupported == []
    assert unconfirmed == []


def test_validate_extracted_findings_reports_unknown_source_label() -> None:
    chunks = [_retrieved_chunk("chunk_1", "A forrásban ez a mondat szerepel.")]

    findings, unsupported, unconfirmed = validate_extracted_findings(
        {
            "findings": [
                {
                    "title": "Rossz címke",
                    "finding_text": "A forrásban ez a mondat szerepel.",
                    "suggested_type": "claim",
                    "relevance_reason": "A fókuszhoz kapcsolódna.",
                    "quote_text": "A forrásban ez a mondat szerepel.",
                    "source_label": "chunk_9",
                }
            ],
        },
        chunks,
    )

    assert findings == []
    assert unconfirmed == []
    assert unsupported == ["chunk_9: ismeretlen source_label; elérhető címkék: chunk_1"]

def test_build_detect_contradiction_candidates_user_prompt_handles_empty_focus() -> None:
    claims = [
        _retrieved_claim("claim_1", "A hivas 18:42-kor tortent."),
        _retrieved_claim("claim_2", "A hivas 19:10-kor tortent."),
    ]
    pairs = [ClaimPair(label="pair_1", claim_a=claims[0], claim_b=claims[1])]

    prompt = build_detect_contradiction_candidates_user_prompt(None, pairs, max_candidates=3)

    assert "QUERY:\nNincs külön fókusz." in prompt
    assert "MAX_CANDIDATES:\n3" in prompt
    assert "CLAIM_PAIRS" in prompt
    assert "pair_1:" in prompt
    assert "claim_label_a: claim_1" in prompt
    assert "claim_label_b: claim_2" in prompt
    assert "Conflict rules:" not in prompt
    assert "Unsupported items:" not in prompt
    assert "Pair and label rules:" not in prompt
    assert "Do not state that the contradiction is proven" not in prompt
    assert "Avoid text containing double quotes" not in prompt


def test_detect_contradiction_candidates_system_prompt_contains_hungarian_rules() -> None:
    prompt = EXTRACT_CONTRADICTIONS_SYSTEM_PROMPT

    assert "Forráshű ellentmondásjelölt-azonosító komponens vagy." in prompt
    assert "Csak a megadott CLAIM_PAIR blokkokban szereplő állításokat" in prompt
    assert "Vizsgáld meg a megadott CLAIM_PAIR blokkokat a QUERY fókusza szerint." in prompt
    assert "Legfeljebb MAX_CANDIDATES" in prompt
    assert "Csak érvényes JSON objektumot adhatsz vissza." in prompt
    assert '{"contradiction_candidates":[],"unsupported_contradiction_candidates":[]}' in prompt


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


def test_detect_contradiction_candidates_requires_focus_text() -> None:
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


def test_detect_contradiction_candidates_returns_warning_when_not_enough_claims(monkeypatch) -> None:
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


def test_detect_contradiction_candidates_returns_warning_when_llm_json_is_invalid(monkeypatch) -> None:
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
