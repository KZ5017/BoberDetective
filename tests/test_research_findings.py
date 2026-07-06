from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.research_finding import ResearchFindingModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.manual_entry import ManualObjectFromSourceCreate
from app.schemas.research_finding import ResearchFindingAttachSourceRequest, ResearchFindingCreate, ResearchFindingRead
from app.api.v1.research_findings import _source_excerpt
from app.services import research_findings
from app.services.research_findings import (
    ResearchFindingValidationError,
    attach_research_finding_source_to_existing_object,
    convert_research_finding_to_manual_object,
    create_research_finding,
    delete_research_findings,
    delete_research_finding,
    restore_research_finding,
    set_aside_research_finding,
)


class _FakeDb:
    def get(self, model, key):
        return None

    def add(self, item):
        pass

    def flush(self):
        pass

    def commit(self):
        pass

    def refresh(self, item):
        pass


class FakeAuditWriter:
    def __init__(self, *args, **kwargs):
        pass

    def write(self, event):
        pass


def test_research_finding_source_excerpt_can_include_unresolved_context_for_invalid_source() -> None:
    source_text = "Ebben a szovegreszben elvileg keresni kellene a hibas LLM idezetet."

    excerpt, start, end = _source_excerpt(
        source_text,
        "hibas LLM altal adott idezet",
        None,
        None,
        include_unresolved_context=True,
    )

    assert excerpt == source_text
    assert start == 0
    assert end == len(source_text)


def test_research_finding_source_excerpt_hides_unresolved_context_by_default() -> None:
    excerpt, start, end = _source_excerpt(
        "Ebben a szovegreszben nincs pontos idezet.",
        "masik idezet",
        None,
        None,
    )

    assert excerpt is None
    assert start is None
    assert end is None


def test_create_research_finding_requires_title() -> None:
    with pytest.raises(ResearchFindingValidationError):
        create_research_finding(
            _FakeDb(),
            case_id=uuid4(),
            title=" ",
            finding_text="Forráshoz kötött találat.",
            relevance_reason="A fókuszszöveghez kapcsolódik.",
            source_reference_id=uuid4(),
            analysis_run_id=uuid4(),
        )


def test_create_research_finding_requires_finding_text() -> None:
    with pytest.raises(ResearchFindingValidationError):
        create_research_finding(
            _FakeDb(),
            case_id=uuid4(),
            title="Találat",
            finding_text=" ",
            relevance_reason="A fókuszszöveghez kapcsolódik.",
            source_reference_id=uuid4(),
            analysis_run_id=uuid4(),
        )


def test_create_research_finding_requires_relevance_reason() -> None:
    with pytest.raises(ResearchFindingValidationError):
        create_research_finding(
            _FakeDb(),
            case_id=uuid4(),
            title="Találat",
            finding_text="Forráshoz kötött találat.",
            relevance_reason=" ",
            source_reference_id=uuid4(),
            analysis_run_id=uuid4(),
        )


def test_create_research_finding_rejects_unknown_suggested_type() -> None:
    with pytest.raises(ResearchFindingValidationError):
        create_research_finding(
            _FakeDb(),
            case_id=uuid4(),
            title="Találat",
            finding_text="Forráshoz kötött találat.",
            relevance_reason="A fókuszszöveghez kapcsolódik.",
            source_reference_id=uuid4(),
            analysis_run_id=uuid4(),
            suggested_type="verdict",
        )


def test_create_research_finding_requires_analysis_run() -> None:
    with pytest.raises(ResearchFindingValidationError):
        create_research_finding(
            _FakeDb(),
            case_id=uuid4(),
            title="Találat",
            finding_text="Forráshoz kötött találat.",
            relevance_reason="A fókuszszöveghez kapcsolódik.",
            source_reference_id=uuid4(),
            analysis_run_id=uuid4(),
        )


def test_research_finding_schema_accepts_graph_compatible_target_fields() -> None:
    payload = ResearchFindingCreate(
        title="Találat",
        finding_text="Forráshoz kötött találat.",
        relevance_reason="A fókuszszöveghez kapcsolódik.",
        source_reference_id=uuid4(),
        analysis_run_id=uuid4(),
        suggested_type="other",
    )

    model = ResearchFindingModel(
        id=uuid4(),
        case_id=uuid4(),
        analysis_run_id=payload.analysis_run_id,
        source_reference_id=payload.source_reference_id,
        title=payload.title,
        finding_text=payload.finding_text,
        suggested_type=payload.suggested_type,
        suggested_type_reason=None,
        relevance_reason=payload.relevance_reason,
        source_validation_status="source_valid",
        llm_support_status="confirmed",
        conversion_status="not_converted",
        target_object_type=None,
        target_object_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    read = ResearchFindingRead.model_validate(model)

    assert read.title == "Találat"
    assert read.suggested_type == "other"
    assert read.llm_support_status == "confirmed"
    assert read.conversion_status == "not_converted"


def test_convert_research_finding_marks_target_and_preserves_source(monkeypatch) -> None:
    case_id = uuid4()
    finding_id = uuid4()
    source_reference_id = uuid4()
    target_object_id = uuid4()
    finding = ResearchFindingModel(
        id=finding_id,
        case_id=case_id,
        analysis_run_id=uuid4(),
        source_reference_id=source_reference_id,
        title="Találat",
        finding_text="Forráshoz kötött találat.",
        suggested_type="claim",
        suggested_type_reason=None,
        relevance_reason="A fókuszhoz kapcsolódik.",
        source_validation_status="source_valid",
        llm_support_status="confirmed",
        conversion_status="not_converted",
        target_object_type=None,
        target_object_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    source_reference = SourceReferenceModel(
        id=source_reference_id,
        case_id=case_id,
        document_id=uuid4(),
        chunk_id=uuid4(),
        quote_text="forrás idézet",
        source_kind="chunk_quote",
    )

    class FakeDb(_FakeDb):
        def get(self, model, key):
            if model is ResearchFindingModel and key == finding_id:
                return finding
            if model is SourceReferenceModel and key == source_reference_id:
                return source_reference
            return None

    monkeypatch.setattr(research_findings, "ensure_source_reference_document_is_active", lambda *args, **kwargs: None)
    monkeypatch.setattr(research_findings, "DatabaseAuditWriter", FakeAuditWriter)
    monkeypatch.setattr(research_findings, "JsonlAuditWriter", FakeAuditWriter)

    def fake_create_manual_object_from_source_reference(
        db,
        case_id_arg,
        source_reference_id_arg,
        payload,
        input_kind,
        target_source_validation_status="source_valid",
    ):
        assert case_id_arg == case_id
        assert source_reference_id_arg == source_reference_id
        assert payload.object_type == "claim"
        assert input_kind == "manual_research_finding_conversion"
        assert target_source_validation_status == "source_valid"
        return uuid4(), source_reference, "claim", target_object_id

    monkeypatch.setattr(research_findings, "create_manual_object_from_source_reference", fake_create_manual_object_from_source_reference)

    converted, _run_id, converted_source, object_type, object_id = convert_research_finding_to_manual_object(
        FakeDb(),
        case_id,
        finding_id,
        ManualObjectFromSourceCreate(object_type="claim", claim_title="Kézi állítás", claim_text="Kézi állítás leírása."),
    )

    assert converted is finding
    assert converted_source is source_reference
    assert object_type == "claim"
    assert object_id == target_object_id
    assert finding.conversion_status == "converted"
    assert finding.target_object_type == "claim"
    assert finding.target_object_id == target_object_id


def test_attach_research_finding_source_marks_converted_and_preserves_target(monkeypatch) -> None:
    case_id = uuid4()
    finding_id = uuid4()
    source_reference_id = uuid4()
    target_object_id = uuid4()
    run_id = uuid4()
    finding = ResearchFindingModel(
        id=finding_id,
        case_id=case_id,
        analysis_run_id=uuid4(),
        source_reference_id=source_reference_id,
        title="Találat",
        finding_text="Forráshoz kötött találat.",
        suggested_type="entity",
        suggested_type_reason=None,
        relevance_reason="A fókuszhoz kapcsolódik.",
        source_validation_status="source_valid",
        llm_support_status="confirmed",
        conversion_status="not_converted",
        target_object_type=None,
        target_object_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    source_reference = SourceReferenceModel(
        id=source_reference_id,
        case_id=case_id,
        document_id=uuid4(),
        page_id=uuid4(),
        chunk_id=uuid4(),
        quote_text="forrás idézet",
        source_kind="chunk_quote",
    )

    class FakeRun:
        id = run_id

    class FakeDb(_FakeDb):
        def get(self, model, key):
            if model is ResearchFindingModel and key == finding_id:
                return finding
            if model is SourceReferenceModel and key == source_reference_id:
                return source_reference
            return None

    monkeypatch.setattr(research_findings, "ensure_source_reference_document_is_active", lambda *args, **kwargs: None)
    monkeypatch.setattr(research_findings, "start_analysis_run", lambda *args, **kwargs: FakeRun())
    monkeypatch.setattr(research_findings, "add_analysis_run_input", lambda *args, **kwargs: None)
    monkeypatch.setattr(research_findings, "add_analysis_run_output", lambda *args, **kwargs: None)
    monkeypatch.setattr(research_findings, "finish_analysis_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(research_findings, "DatabaseAuditWriter", FakeAuditWriter)
    monkeypatch.setattr(research_findings, "JsonlAuditWriter", FakeAuditWriter)

    def fake_attach_source_reference_to_existing_object(
        db,
        *,
        case_id: object,
        source_reference: object,
        target_object_type: str,
        target_object_id: object,
        run_id: object,
    ):
        assert case_id == expected_case_id
        assert source_reference is expected_source_reference
        assert target_object_type == "entity"
        assert target_object_id == expected_target_object_id
        assert run_id == expected_run_id
        return False, False

    expected_case_id = case_id
    expected_source_reference = source_reference
    expected_target_object_id = target_object_id
    expected_run_id = run_id
    monkeypatch.setattr(research_findings, "attach_source_reference_to_existing_object", fake_attach_source_reference_to_existing_object)

    converted, returned_run_id, converted_source, object_type, object_id, skipped_duplicate, target_reactivated = (
        attach_research_finding_source_to_existing_object(
            FakeDb(),
            case_id,
            finding_id,
            ResearchFindingAttachSourceRequest(target_object_type="entity", target_object_id=target_object_id),
        )
    )

    assert converted is finding
    assert returned_run_id == run_id
    assert converted_source is source_reference
    assert object_type == "entity"
    assert object_id == target_object_id
    assert skipped_duplicate is False
    assert target_reactivated is False
    assert finding.conversion_status == "converted"
    assert finding.target_object_type == "entity"
    assert finding.target_object_id == target_object_id


def test_attach_research_finding_source_rejects_invalid_source() -> None:
    case_id = uuid4()
    finding_id = uuid4()
    finding = ResearchFindingModel(
        id=finding_id,
        case_id=case_id,
        analysis_run_id=uuid4(),
        source_reference_id=uuid4(),
        title="Találat",
        finding_text="Forráshoz kötött találat.",
        suggested_type="entity",
        suggested_type_reason=None,
        relevance_reason="A fókuszhoz kapcsolódik.",
        source_validation_status="source_invalid",
        llm_support_status="unconfirmed",
        conversion_status="not_converted",
        target_object_type=None,
        target_object_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    class FakeDb(_FakeDb):
        def get(self, model, key):
            if model is ResearchFindingModel and key == finding_id:
                return finding
            return None

    with pytest.raises(ResearchFindingValidationError):
        attach_research_finding_source_to_existing_object(
            FakeDb(),
            case_id,
            finding_id,
            ResearchFindingAttachSourceRequest(target_object_type="entity", target_object_id=uuid4()),
        )


def test_attach_research_finding_source_rejects_converted() -> None:
    case_id = uuid4()
    finding_id = uuid4()
    finding = ResearchFindingModel(
        id=finding_id,
        case_id=case_id,
        analysis_run_id=uuid4(),
        source_reference_id=uuid4(),
        title="Találat",
        finding_text="Forráshoz kötött találat.",
        suggested_type="entity",
        suggested_type_reason=None,
        relevance_reason="A fókuszhoz kapcsolódik.",
        source_validation_status="source_valid",
        llm_support_status="confirmed",
        conversion_status="converted",
        target_object_type="entity",
        target_object_id=uuid4(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    class FakeDb(_FakeDb):
        def get(self, model, key):
            if model is ResearchFindingModel and key == finding_id:
                return finding
            return None

    with pytest.raises(ResearchFindingValidationError):
        attach_research_finding_source_to_existing_object(
            FakeDb(),
            case_id,
            finding_id,
            ResearchFindingAttachSourceRequest(target_object_type="entity", target_object_id=uuid4()),
        )


def test_set_aside_research_finding_parks_without_target() -> None:
    case_id = uuid4()
    finding_id = uuid4()
    finding = ResearchFindingModel(
        id=finding_id,
        case_id=case_id,
        analysis_run_id=uuid4(),
        source_reference_id=uuid4(),
        title="Találat",
        finding_text="Forráshoz kötött találat.",
        suggested_type="other",
        suggested_type_reason=None,
        relevance_reason="A fókuszhoz kapcsolódik.",
        source_validation_status="source_valid",
        llm_support_status="confirmed",
        conversion_status="not_converted",
        target_object_type=None,
        target_object_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    class FakeDb(_FakeDb):
        def get(self, model, key):
            if model is ResearchFindingModel and key == finding_id:
                return finding
            return None

    set_aside = set_aside_research_finding(FakeDb(), case_id=case_id, finding_id=finding_id)

    assert set_aside is finding
    assert finding.conversion_status == "ignored"
    assert finding.target_object_type is None
    assert finding.target_object_id is None


def test_restore_research_finding_returns_to_active_worklist() -> None:
    case_id = uuid4()
    finding_id = uuid4()
    finding = ResearchFindingModel(
        id=finding_id,
        case_id=case_id,
        analysis_run_id=uuid4(),
        source_reference_id=uuid4(),
        title="Találat",
        finding_text="Forráshoz kötött találat.",
        suggested_type="other",
        suggested_type_reason=None,
        relevance_reason="A fókuszhoz kapcsolódik.",
        source_validation_status="source_valid",
        llm_support_status="confirmed",
        conversion_status="ignored",
        target_object_type=None,
        target_object_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    class FakeDb(_FakeDb):
        def get(self, model, key):
            if model is ResearchFindingModel and key == finding_id:
                return finding
            return None

    restored = restore_research_finding(FakeDb(), case_id=case_id, finding_id=finding_id)

    assert restored is finding
    assert finding.conversion_status == "not_converted"
    assert finding.target_object_type is None
    assert finding.target_object_id is None


def test_set_aside_research_finding_rejects_converted() -> None:
    case_id = uuid4()
    finding_id = uuid4()
    finding = ResearchFindingModel(
        id=finding_id,
        case_id=case_id,
        analysis_run_id=uuid4(),
        source_reference_id=uuid4(),
        title="Találat",
        finding_text="Forráshoz kötött találat.",
        suggested_type="other",
        suggested_type_reason=None,
        relevance_reason="A fókuszhoz kapcsolódik.",
        source_validation_status="source_valid",
        llm_support_status="confirmed",
        conversion_status="converted",
        target_object_type="claim",
        target_object_id=uuid4(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    class FakeDb(_FakeDb):
        def get(self, model, key):
            if model is ResearchFindingModel and key == finding_id:
                return finding
            return None

    with pytest.raises(ResearchFindingValidationError):
        set_aside_research_finding(FakeDb(), case_id=case_id, finding_id=finding_id)


def test_delete_research_finding_removes_unconverted_worklist_item() -> None:
    case_id = uuid4()
    finding_id = uuid4()
    finding = ResearchFindingModel(
        id=finding_id,
        case_id=case_id,
        analysis_run_id=uuid4(),
        source_reference_id=uuid4(),
        title="Találat",
        finding_text="Forráshoz kötött találat.",
        suggested_type="other",
        suggested_type_reason=None,
        relevance_reason="A fókuszhoz kapcsolódik.",
        source_validation_status="source_valid",
        llm_support_status="confirmed",
        conversion_status="not_converted",
        target_object_type=None,
        target_object_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    deleted = []

    class FakeDb(_FakeDb):
        def get(self, model, key):
            if model is ResearchFindingModel and key == finding_id:
                return finding
            return None

        def delete(self, item):
            deleted.append(item)

    delete_research_finding(FakeDb(), case_id=case_id, finding_id=finding_id)

    assert deleted == [finding]


def test_bulk_delete_research_findings_removes_multiple_worklist_items() -> None:
    case_id = uuid4()
    finding_a = ResearchFindingModel(
        id=uuid4(),
        case_id=case_id,
        analysis_run_id=uuid4(),
        source_reference_id=uuid4(),
        title="Első találat",
        finding_text="Forráshoz kötött találat.",
        suggested_type="other",
        suggested_type_reason=None,
        relevance_reason="A fókuszhoz kapcsolódik.",
        source_validation_status="source_valid",
        llm_support_status="confirmed",
        conversion_status="not_converted",
        target_object_type=None,
        target_object_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    finding_b = ResearchFindingModel(
        id=uuid4(),
        case_id=case_id,
        analysis_run_id=uuid4(),
        source_reference_id=uuid4(),
        title="Második találat",
        finding_text="Forráshoz kötött találat.",
        suggested_type="other",
        suggested_type_reason=None,
        relevance_reason="A fókuszhoz kapcsolódik.",
        source_validation_status="source_valid",
        llm_support_status="confirmed",
        conversion_status="ignored",
        target_object_type=None,
        target_object_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    deleted = []

    class FakeResult:
        def scalars(self):
            return [finding_a, finding_b]

    class FakeDb(_FakeDb):
        def execute(self, statement):
            return FakeResult()

        def delete(self, item):
            deleted.append(item)

    count = delete_research_findings(FakeDb(), case_id=case_id, finding_ids=[finding_a.id, finding_b.id])

    assert count == 2
    assert deleted == [finding_a, finding_b]
