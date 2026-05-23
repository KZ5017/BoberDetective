from types import SimpleNamespace
from uuid import uuid4

from app.models.claim import ClaimModel
from app.models.source_reference import SourceReferenceModel
from app.models.entity import EntityMentionModel, EntityModel
from app.services.analysis_deduplication import find_duplicate_claim, find_duplicate_entity, normalize_for_dedup


class _FakeRows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDb:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, statement):
        return _FakeRows(self._rows)


def test_normalize_for_dedup_compacts_case_and_whitespace() -> None:
    assert normalize_for_dedup("  A   Narrator\nES Dupin  ") == "a narrator es dupin"


def test_find_duplicate_claim_matches_same_source_and_normalized_claim_text() -> None:
    case_id = uuid4()
    document_id = uuid4()
    chunk_id = uuid4()
    claim = ClaimModel(
        id=uuid4(),
        case_id=case_id,
        claim_type="document_fact",
        claim_title="A narrátor és Dupin beszélget.",
        claim_text="A narrátor és Dupin beszélget.",
        created_by_analysis_run_id=uuid4(),
        source_validation_status="source_valid",
        review_status="needs_review",
    )
    source_reference = SourceReferenceModel(
        id=uuid4(),
        case_id=case_id,
        document_id=document_id,
        chunk_id=chunk_id,
        quote_text="A narrátor és Dupin beszélget.",
        source_kind="chunk_quote",
    )

    duplicate = find_duplicate_claim(
        _FakeDb([(claim, source_reference)]),
        case_id=case_id,
        claim_type="document_fact",
        claim_text=" a narrátor   és dupin beszélget. ",
        document_id=document_id,
        chunk_id=chunk_id,
        quote_text="A narrátor és Dupin beszélget.",
    )

    assert duplicate == (claim, source_reference)


def test_find_duplicate_claim_matches_same_claim_from_different_quote() -> None:
    claim = SimpleNamespace(claim_text="A narrátor és Dupin beszélget.")
    source_reference = SimpleNamespace(quote_text="Másik idézet.")

    duplicate = find_duplicate_claim(
        _FakeDb([(claim, source_reference)]),
        case_id=uuid4(),
        claim_type="document_fact",
        claim_text="A narrátor és Dupin beszélget.",
        document_id=uuid4(),
        chunk_id=uuid4(),
        quote_text="A narrátor és Dupin beszélget.",
    )

    assert duplicate == (claim, source_reference)


def test_find_duplicate_claim_rejects_different_claim_text() -> None:
    claim = SimpleNamespace(claim_text="A narrátor és Dupin beszélget.")
    source_reference = SimpleNamespace(quote_text="A narrátor és Dupin beszélget.")

    duplicate = find_duplicate_claim(
        _FakeDb([(claim, source_reference)]),
        case_id=uuid4(),
        claim_type="document_fact",
        claim_text="Dupin egyedül távozik.",
        document_id=uuid4(),
        chunk_id=uuid4(),
        quote_text="Dupin egyedül távozik.",
    )

    assert duplicate is None


def test_find_duplicate_entity_matches_same_canonical_name_from_different_mention() -> None:
    entity = EntityModel(
        id=uuid4(),
        case_id=uuid4(),
        entity_type="person",
        canonical_name="C. Auguste Dupin",
        normalized_value=None,
        created_by_analysis_run_id=uuid4(),
        review_status="needs_review",
    )
    mention = EntityMentionModel(
        id=uuid4(),
        case_id=entity.case_id,
        entity_id=entity.id,
        document_id=uuid4(),
        surface_text="Dupin",
        source_reference_id=uuid4(),
        created_by_analysis_run_id=uuid4(),
    )
    source_reference = SourceReferenceModel(
        id=mention.source_reference_id,
        case_id=entity.case_id,
        document_id=mention.document_id,
        chunk_id=uuid4(),
        quote_text="Dupin belépett.",
        source_kind="chunk_quote",
    )

    duplicate = find_duplicate_entity(
        _FakeDb([(entity, mention, source_reference)]),
        case_id=entity.case_id,
        entity_type="person",
        canonical_name="c. auguste   dupin",
        surface_text="Auguste Dupin",
        document_id=uuid4(),
        chunk_id=uuid4(),
        quote_text="Auguste Dupin később megszólalt.",
    )

    assert duplicate == (entity, mention, source_reference)


def test_find_duplicate_entity_does_not_guess_person_alias() -> None:
    entity = EntityModel(
        id=uuid4(),
        case_id=uuid4(),
        entity_type="person",
        canonical_name="C. Auguste Dupin",
        normalized_value=None,
        created_by_analysis_run_id=uuid4(),
        review_status="needs_review",
    )
    mention = EntityMentionModel(
        id=uuid4(),
        case_id=entity.case_id,
        entity_id=entity.id,
        document_id=uuid4(),
        surface_text="C. Auguste Dupin",
        source_reference_id=uuid4(),
        created_by_analysis_run_id=uuid4(),
    )
    source_reference = SourceReferenceModel(
        id=mention.source_reference_id,
        case_id=entity.case_id,
        document_id=mention.document_id,
        chunk_id=uuid4(),
        quote_text="C. Auguste Dupin belépett.",
        source_kind="chunk_quote",
    )

    duplicate = find_duplicate_entity(
        _FakeDb([(entity, mention, source_reference)]),
        case_id=entity.case_id,
        entity_type="person",
        canonical_name="Dupin",
        surface_text="Dupin",
        document_id=uuid4(),
        chunk_id=uuid4(),
        quote_text="Dupin később megszólalt.",
    )

    assert duplicate is None
