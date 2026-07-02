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
    RelationshipRelatedByDocumentResponse,
    RelationshipRelatedDocument,
    RelationshipRelatedObject,
    RelationshipRelatedSourceObject,
)
from app.services.review_report import _entity_source_validation_status
from app.services.text_store import read_chunk_text_from_store, read_page_text_from_store


SUPPORTED_FOCUS_OBJECT_TYPES = {"claim", "event", "entity", "missing_item_candidate", "contradiction_candidate"}
MAX_FOCUS_OBJECTS = 50


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
) -> RelationshipGraph:
    return build_relationship_graph_for_objects(
        db,
        case_id=case_id,
        focus_objects=[RelationshipGraphFocusObject(object_type=object_type, object_id=object_id)],
    )


def build_relationship_graph_for_objects(
    db: Session,
    *,
    case_id: UUID,
    focus_objects: list[RelationshipGraphFocusObject],
) -> RelationshipGraph:
    requested_focuses = _deduplicate_focus_objects(focus_objects)
    if not requested_focuses:
        raise RelationshipGraphValidationError("At least one graph focus object is required")
    if len(requested_focuses) > MAX_FOCUS_OBJECTS:
        raise RelationshipGraphValidationError("Too many graph focus objects")
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


    nodes = list(builder.nodes.values())
    edges = list(builder.edges.values())

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
            max_nodes=len(nodes),
            max_edges=len(edges),
            node_count=len(nodes),
            edge_count=len(edges),
            truncated=False,
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
                page_node_id = _add_page_node(db, builder, page)
                if document_node_id is not None:
                    builder.add_edge("DOCUMENT_HAS_PAGE", document_node_id, page_node_id, "oldal")
            builder.add_node(
                RelationshipGraphNode(
                    id=chunk_node_id,
                    type="chunk",
                    label=f"{chunk.chunk_index}. szövegrész",
                    subtitle=read_chunk_text_from_store(db, chunk),
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
            page_node_id = _add_page_node(db, builder, page)
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


def _add_page_node(db: Session, builder: _GraphBuilder, page: DocumentPageModel) -> str:
    page_node_id = _node_id("page", page.id)
    builder.add_node(
        RelationshipGraphNode(
            id=page_node_id,
            type="page",
            label=f"{page.page_number}. oldal",
            subtitle=read_page_text_from_store(db, page),
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


@dataclass
class _RelatedAccumulator:
    focus: FocusObject
    document_ids: set[UUID]


def find_related_objects_by_documents(
    db: Session,
    *,
    case_id: UUID,
    object_type: str,
    object_id: UUID,
    max_results: int = 100,
) -> RelationshipRelatedByDocumentResponse:
    source_focus = _load_valid_focus_object(db, case_id, object_type, object_id)
    document_ids = _document_ids_for_focus(db, case_id, source_focus)
    related = _related_objects_for_documents(db, case_id, source_focus, document_ids)
    ordered = sorted(
        related.values(),
        key=lambda item: (-len(item.document_ids), item.focus.object_type, item.focus.title.lower()),
    )[:max_results]
    return RelationshipRelatedByDocumentResponse(
        case_id=case_id,
        source_object=RelationshipRelatedSourceObject(
            object_type=source_focus.object_type,
            object_id=source_focus.object_id,
            title=source_focus.title,
        ),
        documents=_related_documents(db, document_ids),
        objects=[
            RelationshipRelatedObject(
                object_type=item.focus.object_type,
                object_id=item.focus.object_id,
                title=item.focus.title,
                body_excerpt=item.focus.body,
                review_status=item.focus.review_status,
                source_validation_status=item.focus.source_validation_status,
                shared_document_count=len(item.document_ids),
                shared_documents=_related_documents(db, item.document_ids),
            )
            for item in ordered
        ],
    )


def _document_ids_for_focus(db: Session, case_id: UUID, focus: FocusObject) -> set[UUID]:
    document_ids = _document_ids_for_source_links(db, case_id, _source_links_for_focus(db, focus))
    if focus.object_type == "contradiction_candidate" and isinstance(focus.model, ContradictionCandidateModel):
        for claim_id in (focus.model.claim_id_a, focus.model.claim_id_b):
            if claim_id is None:
                continue
            claim = db.get(ClaimModel, claim_id)
            if claim is None or claim.case_id != case_id:
                continue
            document_ids.update(_document_ids_for_source_links(db, case_id, _source_links_for_focus(db, _focus_from_claim(claim))))
    return document_ids


def _document_ids_for_source_links(db: Session, case_id: UUID, source_links: Iterable[SourceLink]) -> set[UUID]:
    document_ids: set[UUID] = set()
    for link in source_links:
        source_reference = db.get(SourceReferenceModel, link.source_reference_id)
        if source_reference is not None and source_reference.case_id == case_id and source_reference.document_id is not None:
            document_ids.add(source_reference.document_id)
    return document_ids


def _related_documents(db: Session, document_ids: Iterable[UUID]) -> list[RelationshipRelatedDocument]:
    documents: list[RelationshipRelatedDocument] = []
    for document_id in sorted(set(document_ids), key=str):
        document = db.get(DocumentModel, document_id)
        if document is None:
            continue
        documents.append(RelationshipRelatedDocument(document_id=document.id, filename=document.original_filename))
    return documents


def _related_objects_for_documents(
    db: Session,
    case_id: UUID,
    source_focus: FocusObject,
    document_ids: set[UUID],
) -> dict[tuple[str, UUID], _RelatedAccumulator]:
    related: dict[tuple[str, UUID], _RelatedAccumulator] = {}
    if not document_ids:
        return related

    def add_related(focus: FocusObject | None, document_id: UUID | None) -> None:
        if focus is None or document_id is None:
            return
        if focus.object_type == source_focus.object_type and focus.object_id == source_focus.object_id:
            return
        if focus.source_validation_status != "source_valid":
            return
        if document_id not in document_ids:
            return
        key = (focus.object_type, focus.object_id)
        if key not in related:
            related[key] = _RelatedAccumulator(focus=focus, document_ids=set())
        related[key].document_ids.add(document_id)

    for link in db.execute(select(ClaimSourceModel)).scalars():
        source_reference = db.get(SourceReferenceModel, link.source_reference_id)
        claim = db.get(ClaimModel, link.claim_id)
        if source_reference is not None and source_reference.case_id == case_id and claim is not None and claim.case_id == case_id:
            add_related(_focus_from_model(db, case_id, "claim", claim), source_reference.document_id)

    for link in db.execute(select(EventSourceModel)).scalars():
        source_reference = db.get(SourceReferenceModel, link.source_reference_id)
        event = db.get(EventModel, link.event_id)
        if source_reference is not None and source_reference.case_id == case_id and event is not None and event.case_id == case_id:
            add_related(_focus_from_model(db, case_id, "event", event), source_reference.document_id)

    for link in db.execute(select(MissingItemCandidateSourceModel)).scalars():
        source_reference = db.get(SourceReferenceModel, link.source_reference_id)
        candidate = db.get(MissingItemCandidateModel, link.missing_item_candidate_id)
        if source_reference is not None and source_reference.case_id == case_id and candidate is not None and candidate.case_id == case_id:
            add_related(_focus_from_model(db, case_id, "missing_item_candidate", candidate), source_reference.document_id)

    for mention in db.execute(select(EntityMentionModel)).scalars():
        entity = db.get(EntityModel, mention.entity_id)
        source_reference = db.get(SourceReferenceModel, mention.source_reference_id) if mention.source_reference_id is not None else None
        document_id = source_reference.document_id if source_reference is not None else mention.document_id
        if entity is not None and entity.case_id == case_id and mention.case_id == case_id:
            add_related(_focus_from_model(db, case_id, "entity", entity), document_id)

    for link in db.execute(select(ContradictionCandidateSourceModel)).scalars():
        source_reference = db.get(SourceReferenceModel, link.source_reference_id)
        candidate = db.get(ContradictionCandidateModel, link.contradiction_candidate_id)
        if source_reference is not None and source_reference.case_id == case_id and candidate is not None and candidate.case_id == case_id:
            add_related(_focus_from_model(db, case_id, "contradiction_candidate", candidate), source_reference.document_id)

    return related
