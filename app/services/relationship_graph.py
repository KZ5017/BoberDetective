from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.claim import ClaimModel, ClaimSourceModel
from app.models.contradiction import ContradictionCandidateModel, ContradictionCandidateSourceModel
from app.models.document import DocumentChunkModel, DocumentModel, DocumentPageModel
from app.models.entity import EntityMentionModel, EntityModel
from app.models.event import EventModel, EventSourceModel
from app.models.missing_item import MissingItemCandidateModel, MissingItemCandidateSourceModel
from app.models.source_reference import SourceReferenceModel
from app.schemas.relationship_graph import (
    RelationshipGraph,
    RelationshipGraphEdge,
    RelationshipGraphFocusObject,
    RelationshipGraphLimits,
    RelationshipGraphNode,
    RelationshipGraphNodeStatus,
    RelationshipGraphWarning,
)
from app.services.review_report import _entity_source_validation_status


SUPPORTED_FOCUS_OBJECT_TYPES = {"claim", "event", "entity", "missing_item_candidate", "contradiction_candidate"}
MAX_BACKEND_NODES = 120
MAX_BACKEND_EDGES = 200
MAX_MULTI_FOCUS_BACKEND_NODES = 200
MAX_MULTI_FOCUS_BACKEND_EDGES = 350
MAX_FOCUS_OBJECTS = 20
SHARED_SOURCE_OBJECT_LIMIT = 10


class RelationshipGraphError(ValueError):
    pass


class RelationshipGraphNotFoundError(RelationshipGraphError):
    pass


class RelationshipGraphValidationError(RelationshipGraphError):
    pass


@dataclass(frozen=True)
class FocusObject:
    object_type: str
    object_id: UUID
    model: object
    title: str
    body: str | None
    subtype: str | None
    review_status: str | None
    source_validation_status: str | None


@dataclass(frozen=True)
class SourceLink:
    source_reference_id: UUID
    source_link_id: UUID | None = None
    source_link_type: str | None = None
    support_type: str | None = None
    relevance_rank: int | None = None
    side_label: str | None = None


class _GraphBuilder:
    def __init__(self) -> None:
        self.nodes: dict[str, RelationshipGraphNode] = {}
        self.edges: dict[str, RelationshipGraphEdge] = {}
        self.warnings: list[RelationshipGraphWarning] = []

    def add_node(self, node: RelationshipGraphNode) -> None:
        existing = self.nodes.get(node.id)
        if existing is None:
            self.nodes[node.id] = node
            return
        if node.metadata.get("is_focus"):
            existing.metadata.update(node.metadata)
            existing.metadata["is_focus"] = True

    def add_edge(self, edge_type: str, source: str, target: str, label: str, metadata: dict | None = None) -> None:
        edge_id = f"{source}--{edge_type}--{target}"
        self.edges.setdefault(
            edge_id,
            RelationshipGraphEdge(
                id=edge_id,
                type=edge_type,
                source=source,
                target=target,
                label=label,
                metadata=metadata or {},
            ),
        )


def build_relationship_graph(
    db: Session,
    *,
    case_id: UUID,
    object_type: str,
    object_id: UUID,
    include_shared_sources: bool = True,
    max_nodes: int = 80,
    max_edges: int = 120,
) -> RelationshipGraph:
    return build_relationship_graph_for_objects(
        db,
        case_id=case_id,
        focus_objects=[RelationshipGraphFocusObject(object_type=object_type, object_id=object_id)],
        include_shared_sources=include_shared_sources,
        max_nodes=max_nodes,
        max_edges=max_edges,
        max_backend_nodes=MAX_BACKEND_NODES,
        max_backend_edges=MAX_BACKEND_EDGES,
    )


def build_relationship_graph_for_objects(
    db: Session,
    *,
    case_id: UUID,
    focus_objects: list[RelationshipGraphFocusObject],
    include_shared_sources: bool = True,
    max_nodes: int = 150,
    max_edges: int = 250,
    max_backend_nodes: int = MAX_MULTI_FOCUS_BACKEND_NODES,
    max_backend_edges: int = MAX_MULTI_FOCUS_BACKEND_EDGES,
) -> RelationshipGraph:
    requested_focuses = _deduplicate_focus_objects(focus_objects)
    if not requested_focuses:
        raise RelationshipGraphValidationError("At least one graph focus object is required")
    if len(requested_focuses) > MAX_FOCUS_OBJECTS:
        raise RelationshipGraphValidationError("Too many graph focus objects")

    effective_max_nodes = min(max(1, max_nodes), max_backend_nodes)
    effective_max_edges = min(max(1, max_edges), max_backend_edges)
    builder = _GraphBuilder()
    loaded_focuses: list[FocusObject] = []
    focus_node_ids: list[str] = []

    for requested_focus in requested_focuses:
        focus = _load_valid_focus_object(db, case_id, requested_focus.object_type, requested_focus.object_id)
        loaded_focuses.append(focus)
        focus_node_id = _node_id(focus.object_type, focus.object_id)
        focus_node_ids.append(focus_node_id)
        builder.add_node(
            _object_node(
                focus.object_type,
                focus.object_id,
                focus.title,
                focus.body,
                focus.subtype,
                focus.review_status,
                focus.source_validation_status,
                True,
            )
        )

        source_links = _source_links_for_focus(db, focus)
        if focus.object_type != "contradiction_candidate":
            _add_source_chain(db, builder, case_id, focus_node_id, source_links)

        if focus.object_type == "claim":
            _add_contradiction_neighbors_for_claim(db, builder, case_id, focus.model, focus_node_id)
        elif focus.object_type == "contradiction_candidate":
            _add_claim_pair_for_contradiction(db, builder, case_id, focus.model, focus_node_id)

        if include_shared_sources and focus.object_type != "contradiction_candidate":
            _add_shared_source_neighbors(db, builder, case_id, focus, focus_node_id, source_links)

    nodes = list(builder.nodes.values())
    edges = list(builder.edges.values())
    truncated = len(nodes) > effective_max_nodes or len(edges) > effective_max_edges
    if truncated:
        builder.warnings.append(
            RelationshipGraphWarning(
                code="graph_truncated",
                message="A kapcsolati térkép elemszám-limit miatt rövidítve lett.",
            )
        )
        allowed_node_ids = {node.id for node in nodes[:effective_max_nodes]}
        nodes = [node for node in nodes if node.id in allowed_node_ids]
        edges = [edge for edge in edges if edge.source in allowed_node_ids and edge.target in allowed_node_ids][:effective_max_edges]

    primary_focus = loaded_focuses[0]
    return RelationshipGraph(
        case_id=case_id,
        focus_node_id=focus_node_ids[0],
        focus_object_type=primary_focus.object_type,
        focus_object_id=primary_focus.object_id,
        focus_node_ids=focus_node_ids,
        focus_objects=[
            RelationshipGraphFocusObject(object_type=focus.object_type, object_id=focus.object_id)
            for focus in loaded_focuses
        ],
        nodes=nodes,
        edges=edges,
        warnings=builder.warnings,
        limits=RelationshipGraphLimits(
            max_nodes=effective_max_nodes,
            max_edges=effective_max_edges,
            node_count=len(nodes),
            edge_count=len(edges),
            truncated=truncated,
        ),
    )


def _deduplicate_focus_objects(focus_objects: list[RelationshipGraphFocusObject]) -> list[RelationshipGraphFocusObject]:
    seen: set[tuple[str, UUID]] = set()
    deduplicated: list[RelationshipGraphFocusObject] = []
    for focus in focus_objects:
        key = (focus.object_type, focus.object_id)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(focus)
    return deduplicated


def _load_valid_focus_object(db: Session, case_id: UUID, object_type: str, object_id: UUID) -> FocusObject:
    if object_type not in SUPPORTED_FOCUS_OBJECT_TYPES:
        raise RelationshipGraphValidationError("Unsupported graph focus object type")
    focus = _load_focus_object(db, case_id, object_type, object_id)
    if focus.source_validation_status != "source_valid":
        raise RelationshipGraphValidationError(
            "Ehhez az objektumhoz nincs érvényes forráshivatkozás, ezért első körben nem nyitható kapcsolati térkép."
        )
    return focus


def _node_id(node_type: str, object_id: UUID) -> str:
    return f"{node_type}:{object_id}"


def _object_node(
    object_type: str,
    object_id: UUID,
    title: str,
    body: str | None,
    subtype: str | None,
    review_status: str | None,
    source_validation_status: str | None,
    is_focus: bool = False,
) -> RelationshipGraphNode:
    return RelationshipGraphNode(
        id=_node_id(object_type, object_id),
        type=object_type,
        label=title,
        subtitle=body,
        status=RelationshipGraphNodeStatus(
            review_status=review_status,
            source_validation_status=source_validation_status,
        ),
        metadata={"subtype": subtype, "is_focus": is_focus},
    )


def _load_focus_object(db: Session, case_id: UUID, object_type: str, object_id: UUID) -> FocusObject:
    if object_type == "claim":
        claim = db.get(ClaimModel, object_id)
        if claim is None or claim.case_id != case_id:
            raise RelationshipGraphNotFoundError("Graph focus object not found")
        return FocusObject(
            object_type="claim",
            object_id=claim.id,
            model=claim,
            title=claim.claim_title,
            body=claim.claim_text,
            subtype=claim.claim_type,
            review_status=claim.review_status,
            source_validation_status=claim.source_validation_status,
        )
    if object_type == "event":
        event = db.get(EventModel, object_id)
        if event is None or event.case_id != case_id:
            raise RelationshipGraphNotFoundError("Graph focus object not found")
        return FocusObject(
            object_type="event",
            object_id=event.id,
            model=event,
            title=event.event_title,
            body=event.event_description,
            subtype=event.event_type,
            review_status=event.review_status,
            source_validation_status=event.source_validation_status,
        )
    if object_type == "missing_item_candidate":
        candidate = db.get(MissingItemCandidateModel, object_id)
        if candidate is None or candidate.case_id != case_id:
            raise RelationshipGraphNotFoundError("Graph focus object not found")
        return FocusObject(
            object_type="missing_item_candidate",
            object_id=candidate.id,
            model=candidate,
            title=candidate.referenced_item_text,
            body=candidate.description,
            subtype=candidate.missing_item_type,
            review_status=candidate.review_status,
            source_validation_status=candidate.source_validation_status,
        )
    if object_type == "contradiction_candidate":
        candidate = db.get(ContradictionCandidateModel, object_id)
        if candidate is None or candidate.case_id != case_id:
            raise RelationshipGraphNotFoundError("Graph focus object not found")
        return FocusObject(
            object_type="contradiction_candidate",
            object_id=candidate.id,
            model=candidate,
            title=candidate.title,
            body=candidate.description,
            subtype=candidate.contradiction_type,
            review_status=candidate.review_status,
            source_validation_status=candidate.source_validation_status,
        )
    if object_type == "entity":
        entity = db.get(EntityModel, object_id)
        if entity is None or entity.case_id != case_id:
            raise RelationshipGraphNotFoundError("Graph focus object not found")
        return FocusObject(
            object_type="entity",
            object_id=entity.id,
            model=entity,
            title=entity.canonical_name,
            body=entity.description,
            subtype=entity.entity_type,
            review_status=entity.review_status,
            source_validation_status=_entity_source_validation_status(db, case_id, entity.id),
        )
    raise RelationshipGraphValidationError("Unsupported graph focus object type")


def _source_links_for_focus(db: Session, focus: FocusObject) -> list[SourceLink]:
    if focus.object_type == "claim":
        rows = db.execute(
            select(ClaimSourceModel)
            .where(ClaimSourceModel.claim_id == focus.object_id)
            .order_by(ClaimSourceModel.relevance_rank.asc().nullslast())
        ).scalars()
        return [
            SourceLink(row.source_reference_id, row.id, "claim_source", row.support_type, row.relevance_rank)
            for row in rows
        ]
    if focus.object_type == "event":
        rows = db.execute(
            select(EventSourceModel)
            .where(EventSourceModel.event_id == focus.object_id)
            .order_by(EventSourceModel.relevance_rank.asc().nullslast())
        ).scalars()
        return [
            SourceLink(row.source_reference_id, row.id, "event_source", row.support_type, row.relevance_rank)
            for row in rows
        ]
    if focus.object_type == "missing_item_candidate":
        rows = db.execute(
            select(MissingItemCandidateSourceModel)
            .where(MissingItemCandidateSourceModel.missing_item_candidate_id == focus.object_id)
            .order_by(MissingItemCandidateSourceModel.relevance_rank.asc().nullslast())
        ).scalars()
        return [
            SourceLink(row.source_reference_id, row.id, "missing_item_candidate_source", "direct", row.relevance_rank)
            for row in rows
        ]
    if focus.object_type == "contradiction_candidate":
        rows = db.execute(
            select(ContradictionCandidateSourceModel)
            .where(ContradictionCandidateSourceModel.contradiction_candidate_id == focus.object_id)
            .order_by(ContradictionCandidateSourceModel.side_label.asc().nullslast())
        ).scalars()
        return [
            SourceLink(row.source_reference_id, row.id, "contradiction_candidate_source", row.side_label or "contextual", side_label=row.side_label)
            for row in rows
        ]
    if focus.object_type == "entity":
        rows = db.execute(
            select(EntityMentionModel)
            .where(EntityMentionModel.entity_id == focus.object_id, EntityMentionModel.source_reference_id.is_not(None))
            .order_by(EntityMentionModel.created_at.asc())
        ).scalars()
        return [
            SourceLink(row.source_reference_id, row.id, "entity_mention", "direct")
            for row in rows
            if row.source_reference_id is not None
        ]
    return []


def _add_source_chain(db: Session, builder: _GraphBuilder, case_id: UUID, object_node_id: str, links: Iterable[SourceLink]) -> None:
    for link in links:
        source_reference = db.get(SourceReferenceModel, link.source_reference_id)
        if source_reference is None or source_reference.case_id != case_id:
            continue
        source_node_id = _node_id("source_reference", source_reference.id)
        builder.add_node(
            RelationshipGraphNode(
                id=source_node_id,
                type="source_reference",
                label=source_reference.citation_label or source_reference.quote_text[:90],
                subtitle=source_reference.quote_text,
                status=RelationshipGraphNodeStatus(source_validation_status="source_valid"),
                metadata={
                    "source_kind": source_reference.source_kind,
                    "page_number": source_reference.page_number,
                    "quote_char_start": source_reference.quote_char_start,
                    "quote_char_end": source_reference.quote_char_end,
                    "source_link_id": str(link.source_link_id) if link.source_link_id else None,
                    "source_link_type": link.source_link_type,
                    "support_type": link.support_type,
                    "relevance_rank": link.relevance_rank,
                    "side_label": link.side_label,
                },
            )
        )
        builder.add_edge("HAS_SOURCE", object_node_id, source_node_id, "forrása", {"support_type": link.support_type})
        _add_source_location_nodes(db, builder, source_node_id, source_reference)


def _add_source_location_nodes(
    db: Session,
    builder: _GraphBuilder,
    source_node_id: str,
    source_reference: SourceReferenceModel,
) -> None:
    document_node_id: str | None = None
    page_node_id: str | None = None
    chunk_node_id: str | None = None
    document = db.get(DocumentModel, source_reference.document_id)
    if document is not None:
        document_node_id = _node_id("document", document.id)
        builder.add_node(
            RelationshipGraphNode(
                id=document_node_id,
                type="document",
                label=document.original_filename,
                subtitle=document.sha256_hash,
                metadata={
                    "processing_status": document.processing_status,
                    "lifecycle_status": document.lifecycle_status,
                    "page_count": document.page_count,
                },
            )
        )
    if source_reference.chunk_id is not None:
        chunk = db.get(DocumentChunkModel, source_reference.chunk_id)
        if chunk is not None:
            chunk_node_id = _node_id("chunk", chunk.id)
            page = _resolve_source_location_page(db, source_reference, chunk)
            if page is not None:
                page_node_id = _add_page_node(builder, page)
                if document_node_id is not None:
                    builder.add_edge("DOCUMENT_HAS_PAGE", document_node_id, page_node_id, "oldal")
            builder.add_node(
                RelationshipGraphNode(
                    id=chunk_node_id,
                    type="chunk",
                    label=f"{chunk.chunk_index}. szövegrész",
                    subtitle=f"{chunk.page_start}-{chunk.page_end}. oldal",
                    metadata={
                        "chunk_index": chunk.chunk_index,
                        "page_start": chunk.page_start,
                        "page_end": chunk.page_end,
                        "char_start": chunk.char_start,
                        "char_end": chunk.char_end,
                    },
                )
            )
            if page_node_id is not None:
                builder.add_edge("PAGE_HAS_CHUNK", page_node_id, chunk_node_id, "szövegrész")
            elif document_node_id is not None:
                builder.add_edge("DOCUMENT_HAS_CHUNK", document_node_id, chunk_node_id, "szövegrész")
    elif source_reference.page_id is not None:
        page = db.get(DocumentPageModel, source_reference.page_id)
        if page is not None:
            page_node_id = _add_page_node(builder, page)
            if document_node_id is not None:
                builder.add_edge("DOCUMENT_HAS_PAGE", document_node_id, page_node_id, "oldal")
    if chunk_node_id is not None:
        builder.add_edge("SOURCE_FROM_CHUNK", chunk_node_id, source_node_id, "forráshivatkozás")
    elif page_node_id is not None:
        builder.add_edge("SOURCE_FROM_PAGE", page_node_id, source_node_id, "forráshivatkozás")
    elif document_node_id is not None:
        builder.add_edge("SOURCE_FROM_DOCUMENT", document_node_id, source_node_id, "forráshivatkozás")


def _resolve_source_location_page(
    db: Session,
    source_reference: SourceReferenceModel,
    chunk: DocumentChunkModel,
) -> DocumentPageModel | None:
    if source_reference.page_id is not None:
        page = db.get(DocumentPageModel, source_reference.page_id)
        if page is not None:
            return page
    if chunk.page_start != chunk.page_end:
        return None
    return db.execute(
        select(DocumentPageModel).where(
            DocumentPageModel.case_id == source_reference.case_id,
            DocumentPageModel.document_id == source_reference.document_id,
            DocumentPageModel.page_number == chunk.page_start,
            DocumentPageModel.is_current.is_(True),
        )
    ).scalars().first()


def _add_page_node(builder: _GraphBuilder, page: DocumentPageModel) -> str:
    page_node_id = _node_id("page", page.id)
    builder.add_node(
        RelationshipGraphNode(
            id=page_node_id,
            type="page",
            label=f"{page.page_number}. oldal",
            subtitle=page.text_source,
            metadata={"page_number": page.page_number, "text_source": page.text_source, "ocr_used": page.ocr_used},
        )
    )
    return page_node_id


def _add_contradiction_neighbors_for_claim(
    db: Session,
    builder: _GraphBuilder,
    case_id: UUID,
    claim: ClaimModel,
    claim_node_id: str,
) -> None:
    candidates = db.execute(
        select(ContradictionCandidateModel)
        .where(
            ContradictionCandidateModel.case_id == case_id,
            or_(ContradictionCandidateModel.claim_id_a == claim.id, ContradictionCandidateModel.claim_id_b == claim.id),
        )
        .order_by(ContradictionCandidateModel.created_at.desc())
    ).scalars()
    for candidate in candidates:
        candidate_node_id = _node_id("contradiction_candidate", candidate.id)
        builder.add_node(
            _object_node(
                "contradiction_candidate",
                candidate.id,
                candidate.title,
                candidate.description,
                candidate.contradiction_type,
                candidate.review_status,
                candidate.source_validation_status,
            )
        )
        edge_type = "CONTRADICTS_CLAIM_A" if candidate.claim_id_a == claim.id else "CONTRADICTS_CLAIM_B"
        builder.add_edge(edge_type, claim_node_id, candidate_node_id, "állítás A" if edge_type.endswith("_A") else "állítás B")


def _add_claim_pair_for_contradiction(
    db: Session,
    builder: _GraphBuilder,
    case_id: UUID,
    candidate: ContradictionCandidateModel,
    candidate_node_id: str,
) -> None:
    for edge_type, claim_id, label in (
        ("CONTRADICTS_CLAIM_A", candidate.claim_id_a, "állítás A"),
        ("CONTRADICTS_CLAIM_B", candidate.claim_id_b, "állítás B"),
    ):
        if claim_id is None:
            continue
        claim = db.get(ClaimModel, claim_id)
        if claim is None or claim.case_id != case_id:
            continue
        claim_node_id = _node_id("claim", claim.id)
        builder.add_node(
            _object_node(
                "claim",
                claim.id,
                claim.claim_title,
                claim.claim_text,
                claim.claim_type,
                claim.review_status,
                claim.source_validation_status,
            )
        )
        builder.add_edge(edge_type, claim_node_id, candidate_node_id, label)
        _add_source_chain(db, builder, case_id, claim_node_id, _source_links_for_focus(db, _focus_from_claim(claim)))


def _focus_from_claim(claim: ClaimModel) -> FocusObject:
    return FocusObject(
        object_type="claim",
        object_id=claim.id,
        model=claim,
        title=claim.claim_title,
        body=claim.claim_text,
        subtype=claim.claim_type,
        review_status=claim.review_status,
        source_validation_status=claim.source_validation_status,
    )


def _add_shared_source_neighbors(
    db: Session,
    builder: _GraphBuilder,
    case_id: UUID,
    focus: FocusObject,
    focus_node_id: str,
    source_links: list[SourceLink],
) -> None:
    count = 0
    for link in source_links:
        for object_type, obj in _objects_sharing_source(db, case_id, focus, link.source_reference_id):
            if count >= SHARED_SOURCE_OBJECT_LIMIT:
                builder.warnings.append(
                    RelationshipGraphWarning(
                        code="shared_source_limit",
                        message="Az azonos forrásból származó kapcsolódó objektumok listája rövidítve lett.",
                    )
                )
                return
            neighbor = _focus_from_model(db, case_id, object_type, obj)
            if neighbor is None:
                continue
            neighbor_node_id = _node_id(neighbor.object_type, neighbor.object_id)
            builder.add_node(
                _object_node(
                    neighbor.object_type,
                    neighbor.object_id,
                    neighbor.title,
                    neighbor.body,
                    neighbor.subtype,
                    neighbor.review_status,
                    neighbor.source_validation_status,
                )
            )
            builder.add_edge("SHARES_SOURCE_WITH", focus_node_id, neighbor_node_id, "azonos forrás", {"source_reference_id": str(link.source_reference_id)})
            count += 1


def _objects_sharing_source(db: Session, case_id: UUID, focus: FocusObject, source_reference_id: UUID) -> list[tuple[str, object]]:
    rows: list[tuple[str, object]] = []
    for source_link in db.execute(select(ClaimSourceModel).where(ClaimSourceModel.source_reference_id == source_reference_id)).scalars():
        claim = db.get(ClaimModel, source_link.claim_id)
        if claim is not None and claim.case_id == case_id and not (focus.object_type == "claim" and claim.id == focus.object_id):
            rows.append(("claim", claim))
    for source_link in db.execute(select(EventSourceModel).where(EventSourceModel.source_reference_id == source_reference_id)).scalars():
        event = db.get(EventModel, source_link.event_id)
        if event is not None and event.case_id == case_id and not (focus.object_type == "event" and event.id == focus.object_id):
            rows.append(("event", event))
    for source_link in db.execute(
        select(MissingItemCandidateSourceModel).where(MissingItemCandidateSourceModel.source_reference_id == source_reference_id)
    ).scalars():
        candidate = db.get(MissingItemCandidateModel, source_link.missing_item_candidate_id)
        if candidate is not None and candidate.case_id == case_id and not (
            focus.object_type == "missing_item_candidate" and candidate.id == focus.object_id
        ):
            rows.append(("missing_item_candidate", candidate))
    for mention in db.execute(select(EntityMentionModel).where(EntityMentionModel.source_reference_id == source_reference_id)).scalars():
        entity = db.get(EntityModel, mention.entity_id)
        if entity is not None and entity.case_id == case_id and not (focus.object_type == "entity" and entity.id == focus.object_id):
            rows.append(("entity", entity))
    return rows


def _focus_from_model(db: Session, case_id: UUID, object_type: str, obj: object) -> FocusObject | None:
    if object_type == "claim" and isinstance(obj, ClaimModel):
        return _focus_from_claim(obj)
    if object_type == "event" and isinstance(obj, EventModel):
        return FocusObject(
            object_type="event",
            object_id=obj.id,
            model=obj,
            title=obj.event_title,
            body=obj.event_description,
            subtype=obj.event_type,
            review_status=obj.review_status,
            source_validation_status=obj.source_validation_status,
        )
    if object_type == "missing_item_candidate" and isinstance(obj, MissingItemCandidateModel):
        return FocusObject(
            object_type="missing_item_candidate",
            object_id=obj.id,
            model=obj,
            title=obj.referenced_item_text,
            body=obj.description,
            subtype=obj.missing_item_type,
            review_status=obj.review_status,
            source_validation_status=obj.source_validation_status,
        )
    if object_type == "entity" and isinstance(obj, EntityModel):
        return FocusObject(
            object_type="entity",
            object_id=obj.id,
            model=obj,
            title=obj.canonical_name,
            body=obj.description,
            subtype=obj.entity_type,
            review_status=obj.review_status,
            source_validation_status=_entity_source_validation_status(db, case_id, obj.id),
        )
    return None
