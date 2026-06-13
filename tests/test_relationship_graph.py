from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.analysis import AnalysisRunModel
from app.models.claim import ClaimModel, ClaimSourceModel
from app.models.contradiction import ContradictionCandidateModel, ContradictionCandidateSourceModel
from app.models.document import DocumentChunkModel, DocumentModel, DocumentPageModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.relationship_graph import RelationshipGraphFocusObject
from app.services.relationship_graph import (
    RelationshipGraphValidationError,
    build_relationship_graph,
    build_relationship_graph_for_objects,
)


class _FakeScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def scalars(self) -> "_FakeScalarResult":
        return self

    def first(self) -> object | None:
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class _FakeSession:
    def __init__(self) -> None:
        self.objects: dict[tuple[type, object], object] = {}
        self.rows: dict[type, list[object]] = {}

    def add_object(self, obj: object, object_id: object) -> None:
        self.objects[(type(obj), object_id)] = obj

    def add_rows(self, model: type, rows: list[object]) -> None:
        self.rows[model] = rows

    def get(self, model: type, object_id: object) -> object | None:
        return self.objects.get((model, object_id))

    def execute(self, statement) -> _FakeScalarResult:
        model = statement.column_descriptions[0].get("entity")
        return _FakeScalarResult(self.rows.get(model, []))


def _seed_claim_graph_session(source_validation_status: str = "source_valid") -> tuple[_FakeSession, dict[str, object]]:
    now = datetime.now(UTC)
    case_id = uuid4()
    user_id = uuid4()
    run_id = uuid4()
    claim_id = uuid4()
    claim_source_id = uuid4()
    source_reference_id = uuid4()
    document_id = uuid4()
    page_id = uuid4()
    chunk_id = uuid4()

    db = _FakeSession()
    run = AnalysisRunModel(
        id=run_id,
        case_id=case_id,
        run_type="manual_entry",
        status="succeeded",
        started_by_user_id=user_id,
        started_at=now,
        model_name=None,
        validation_status="passed",
    )
    claim = ClaimModel(
        id=claim_id,
        case_id=case_id,
        claim_type="document_fact",
        claim_title="A tanú látta az eseményt",
        claim_text="A tanú állítása szerint látta az esemény egyik részletét.",
        created_by_analysis_run_id=run_id,
        source_validation_status=source_validation_status,
        review_status="needs_review",
    )
    claim_source = ClaimSourceModel(
        id=claim_source_id,
        claim_id=claim_id,
        source_reference_id=source_reference_id,
        relevance_rank=0,
        support_type="direct",
    )
    document = DocumentModel(
        id=document_id,
        case_id=case_id,
        original_filename="forras.pdf",
        stored_path="documents/forras.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1234,
        sha256_hash="a" * 64,
        imported_by_user_id=user_id,
        processing_status="processed",
        lifecycle_status="active",
        page_count=1,
    )
    page = DocumentPageModel(
        id=page_id,
        case_id=case_id,
        document_id=document_id,
        page_number=2,
        text_source="native",
        ocr_used=False,
        version_no=1,
        is_current=True,
        text_char_count=120,
    )
    chunk = DocumentChunkModel(
        id=chunk_id,
        case_id=case_id,
        document_id=document_id,
        page_start=2,
        page_end=2,
        chunk_index=0,
        char_start=0,
        char_end=120,
        chunking_strategy="char_window_v2",
        chunker_version="v1",
        version_no=1,
        is_current=True,
    )
    source_reference = SourceReferenceModel(
        id=source_reference_id,
        case_id=case_id,
        document_id=document_id,
        page_id=page_id,
        chunk_id=chunk_id,
        page_number=2,
        quote_text="A tanú állítása szerint látta az esemény egyik részletét.",
        quote_char_start=0,
        quote_char_end=60,
        citation_label="forras.pdf 2. oldal 0. szövegrész",
        source_kind="chunk_quote",
    )

    for obj, object_id in (
        (run, run_id),
        (claim, claim_id),
        (document, document_id),
        (page, page_id),
        (chunk, chunk_id),
        (source_reference, source_reference_id),
    ):
        db.add_object(obj, object_id)
    db.add_rows(ClaimSourceModel, [claim_source])
    db.add_rows(ContradictionCandidateModel, [])
    db.add_rows(DocumentPageModel, [page])

    return db, {
        "case_id": case_id,
        "claim_id": claim_id,
        "run_id": run_id,
        "source_reference_id": source_reference_id,
        "document_id": document_id,
        "page_id": page_id,
        "chunk_id": chunk_id,
    }


def test_relationship_graph_claim_includes_source_location() -> None:
    db, ids = _seed_claim_graph_session()

    graph = build_relationship_graph(
        db,
        case_id=ids["case_id"],
        object_type="claim",
        object_id=ids["claim_id"],
    )

    node_ids = {node.id for node in graph.nodes}
    edge_types = {edge.type for edge in graph.edges}
    assert graph.focus_node_id == f"claim:{ids['claim_id']}"
    assert f"source_reference:{ids['source_reference_id']}" in node_ids
    assert f"document:{ids['document_id']}" in node_ids
    assert f"page:{ids['page_id']}" in node_ids
    assert f"chunk:{ids['chunk_id']}" in node_ids
    assert f"analysis_run:{ids['run_id']}" not in node_ids
    assert {"HAS_SOURCE", "DOCUMENT_HAS_PAGE", "PAGE_HAS_CHUNK", "SOURCE_FROM_CHUNK"}.issubset(edge_types)
    assert "CREATED_BY_RUN" not in edge_types
    assert "FINDING_CONVERTED_TO" not in edge_types
    assert any(
        edge.type == "DOCUMENT_HAS_PAGE"
        and edge.source == f"document:{ids['document_id']}"
        and edge.target == f"page:{ids['page_id']}"
        for edge in graph.edges
    )
    assert any(
        edge.type == "PAGE_HAS_CHUNK"
        and edge.source == f"page:{ids['page_id']}"
        and edge.target == f"chunk:{ids['chunk_id']}"
        for edge in graph.edges
    )
    assert any(
        edge.type == "SOURCE_FROM_CHUNK"
        and edge.source == f"chunk:{ids['chunk_id']}"
        and edge.target == f"source_reference:{ids['source_reference_id']}"
        for edge in graph.edges
    )
    assert graph.focus_node_ids == [f"claim:{ids['claim_id']}"]
    assert len(graph.focus_objects) == 1


def test_relationship_graph_source_location_infers_page_from_chunk() -> None:
    db, ids = _seed_claim_graph_session()
    source_reference = db.get(SourceReferenceModel, ids["source_reference_id"])
    assert source_reference is not None
    source_reference.page_id = None

    graph = build_relationship_graph(
        db,
        case_id=ids["case_id"],
        object_type="claim",
        object_id=ids["claim_id"],
    )

    edge_types = {edge.type for edge in graph.edges}
    assert {"HAS_SOURCE", "DOCUMENT_HAS_PAGE", "PAGE_HAS_CHUNK", "SOURCE_FROM_CHUNK"}.issubset(edge_types)
    assert any(
        edge.type == "DOCUMENT_HAS_PAGE"
        and edge.source == f"document:{ids['document_id']}"
        and edge.target == f"page:{ids['page_id']}"
        for edge in graph.edges
    )
    assert any(
        edge.type == "PAGE_HAS_CHUNK"
        and edge.source == f"page:{ids['page_id']}"
        and edge.target == f"chunk:{ids['chunk_id']}"
        for edge in graph.edges
    )


def test_relationship_graph_source_location_falls_back_to_document_chunk_chain() -> None:
    db, ids = _seed_claim_graph_session()
    source_reference = db.get(SourceReferenceModel, ids["source_reference_id"])
    assert source_reference is not None
    source_reference.page_id = None
    db.add_rows(DocumentPageModel, [])

    graph = build_relationship_graph(
        db,
        case_id=ids["case_id"],
        object_type="claim",
        object_id=ids["claim_id"],
    )

    edge_types = {edge.type for edge in graph.edges}
    assert {"HAS_SOURCE", "DOCUMENT_HAS_CHUNK", "SOURCE_FROM_CHUNK"}.issubset(edge_types)
    assert "DOCUMENT_HAS_PAGE" not in edge_types
    assert "PAGE_HAS_CHUNK" not in edge_types
    assert any(
        edge.type == "DOCUMENT_HAS_CHUNK"
        and edge.source == f"document:{ids['document_id']}"
        and edge.target == f"chunk:{ids['chunk_id']}"
        for edge in graph.edges
    )
    assert any(
        edge.type == "SOURCE_FROM_CHUNK"
        and edge.source == f"chunk:{ids['chunk_id']}"
        and edge.target == f"source_reference:{ids['source_reference_id']}"
        for edge in graph.edges
    )


def test_relationship_graph_multi_focus_deduplicates_shared_source() -> None:
    db, ids = _seed_claim_graph_session()
    second_claim_id = uuid4()
    second_claim_source_id = uuid4()
    second_claim = ClaimModel(
        id=second_claim_id,
        case_id=ids["case_id"],
        claim_type="document_fact",
        claim_title="A második tanú is látta az eseményt",
        claim_text="A második tanú ugyanarra az eseményrészletre utal.",
        created_by_analysis_run_id=ids["run_id"],
        source_validation_status="source_valid",
        review_status="verified",
    )
    second_claim_source = ClaimSourceModel(
        id=second_claim_source_id,
        claim_id=second_claim_id,
        source_reference_id=ids["source_reference_id"],
        relevance_rank=1,
        support_type="direct",
    )
    db.add_object(second_claim, second_claim_id)
    db.add_rows(
        ClaimSourceModel,
        [
            *db.rows[ClaimSourceModel],
            second_claim_source,
        ],
    )

    graph = build_relationship_graph_for_objects(
        db,
        case_id=ids["case_id"],
        focus_objects=[
            RelationshipGraphFocusObject(object_type="claim", object_id=ids["claim_id"]),
            RelationshipGraphFocusObject(object_type="claim", object_id=second_claim_id),
        ],
    )

    node_ids = [node.id for node in graph.nodes]
    nodes_by_id = {node.id: node for node in graph.nodes}
    source_node_id = f"source_reference:{ids['source_reference_id']}"
    assert graph.focus_node_ids == [f"claim:{ids['claim_id']}", f"claim:{second_claim_id}"]
    assert nodes_by_id[f"claim:{ids['claim_id']}"].metadata["is_focus"] is True
    assert nodes_by_id[f"claim:{second_claim_id}"].metadata["is_focus"] is True
    assert node_ids.count(source_node_id) == 1
    assert sum(1 for edge in graph.edges if edge.type == "HAS_SOURCE" and edge.target == source_node_id) == 2


def test_relationship_graph_multi_focus_rejects_source_invalid_focus() -> None:
    db, ids = _seed_claim_graph_session(source_validation_status="source_invalid")

    with pytest.raises(RelationshipGraphValidationError):
        build_relationship_graph_for_objects(
            db,
            case_id=ids["case_id"],
            focus_objects=[RelationshipGraphFocusObject(object_type="claim", object_id=ids["claim_id"])],
        )


def test_relationship_graph_multi_focus_rejects_too_many_focus_objects() -> None:
    db, ids = _seed_claim_graph_session()

    with pytest.raises(RelationshipGraphValidationError):
        build_relationship_graph_for_objects(
            db,
            case_id=ids["case_id"],
            focus_objects=[
                RelationshipGraphFocusObject(object_type="claim", object_id=uuid4())
                for _ in range(21)
            ],
        )


def test_relationship_graph_rejects_source_invalid_focus() -> None:
    db, ids = _seed_claim_graph_session(source_validation_status="source_invalid")

    with pytest.raises(RelationshipGraphValidationError):
        build_relationship_graph(
            db,
            case_id=ids["case_id"],
            object_type="claim",
            object_id=ids["claim_id"],
        )


def test_relationship_graph_contradiction_candidate_includes_claim_pair() -> None:
    now = datetime.now(UTC)
    case_id = uuid4()
    user_id = uuid4()
    run_id = uuid4()
    claim_a_id = uuid4()
    claim_b_id = uuid4()
    candidate_id = uuid4()
    source_reference_id = uuid4()
    document_id = uuid4()
    candidate_source_id = uuid4()
    db = _FakeSession()

    run = AnalysisRunModel(
        id=run_id,
        case_id=case_id,
        run_type="detect_contradiction_candidates",
        status="succeeded",
        started_by_user_id=user_id,
        started_at=now,
        model_name="local-test-model",
        validation_status="passed",
    )
    claim_a = ClaimModel(
        id=claim_a_id,
        case_id=case_id,
        claim_type="document_fact",
        claim_title="Az első állítás",
        claim_text="Az első állítás szövege.",
        created_by_analysis_run_id=run_id,
        source_validation_status="source_valid",
        review_status="needs_review",
    )
    claim_b = ClaimModel(
        id=claim_b_id,
        case_id=case_id,
        claim_type="document_fact",
        claim_title="A második állítás",
        claim_text="A második állítás szövege.",
        created_by_analysis_run_id=run_id,
        source_validation_status="source_valid",
        review_status="verified",
    )
    candidate = ContradictionCandidateModel(
        id=candidate_id,
        case_id=case_id,
        contradiction_type="other",
        title="A két állítás ütközhet",
        description="A két állítás emberi ellenőrzésre váró ütközésjelölt.",
        claim_id_a=claim_a_id,
        claim_id_b=claim_b_id,
        created_by_analysis_run_id=run_id,
        source_validation_status="source_valid",
        review_status="needs_review",
    )
    candidate_source = ContradictionCandidateSourceModel(
        id=candidate_source_id,
        contradiction_candidate_id=candidate_id,
        source_reference_id=source_reference_id,
        side_label="context",
    )
    candidate_source_reference = SourceReferenceModel(
        id=source_reference_id,
        case_id=case_id,
        document_id=document_id,
        page_id=None,
        chunk_id=None,
        page_number=None,
        quote_text="Kontextus forrás az ellentmondásjelölthöz.",
        quote_char_start=None,
        quote_char_end=None,
        citation_label="kontextus forrás",
        source_kind="document_metadata",
    )

    for obj, object_id in (
        (run, run_id),
        (claim_a, claim_a_id),
        (claim_b, claim_b_id),
        (candidate, candidate_id),
        (candidate_source_reference, source_reference_id),
    ):
        db.add_object(obj, object_id)
    db.add_rows(ClaimSourceModel, [])
    db.add_rows(ContradictionCandidateSourceModel, [candidate_source])

    graph = build_relationship_graph(
        db,
        case_id=case_id,
        object_type="contradiction_candidate",
        object_id=candidate_id,
    )

    node_ids = {node.id for node in graph.nodes}
    edge_types = {edge.type for edge in graph.edges}
    assert graph.focus_node_id == f"contradiction_candidate:{candidate_id}"
    assert f"claim:{claim_a_id}" in node_ids
    assert f"claim:{claim_b_id}" in node_ids
    assert {"CONTRADICTS_CLAIM_A", "CONTRADICTS_CLAIM_B"}.issubset(edge_types)
    assert "CREATED_BY_RUN" not in edge_types
    assert any(
        edge.type == "CONTRADICTS_CLAIM_A"
        and edge.source == f"claim:{claim_a_id}"
        and edge.target == f"contradiction_candidate:{candidate_id}"
        for edge in graph.edges
    )
    assert any(
        edge.type == "CONTRADICTS_CLAIM_B"
        and edge.source == f"claim:{claim_b_id}"
        and edge.target == f"contradiction_candidate:{candidate_id}"
        for edge in graph.edges
    )
    assert not any(
        edge.type == "HAS_SOURCE"
        and edge.source == f"contradiction_candidate:{candidate_id}"
        for edge in graph.edges
    )
