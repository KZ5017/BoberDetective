from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RelationshipGraphNodeStatus(BaseModel):
    review_status: str | None = None
    source_validation_status: str | None = None


class RelationshipGraphNode(BaseModel):
    id: str
    type: str
    label: str
    subtitle: str | None = None
    status: RelationshipGraphNodeStatus = Field(default_factory=RelationshipGraphNodeStatus)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RelationshipGraphEdge(BaseModel):
    id: str
    type: str
    source: str
    target: str
    label: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RelationshipGraphWarning(BaseModel):
    code: str
    message: str


class RelationshipGraphLimits(BaseModel):
    max_nodes: int
    max_edges: int
    node_count: int
    edge_count: int
    truncated: bool = False


class RelationshipGraphFocusObject(BaseModel):
    object_type: str
    object_id: UUID


class RelationshipGraphMultiFocusRequest(BaseModel):
    focus_objects: list[RelationshipGraphFocusObject] = Field(min_length=1, max_length=50)


class RelationshipRelatedSourceObject(BaseModel):
    object_type: str
    object_id: UUID
    title: str


class RelationshipRelatedDocument(BaseModel):
    document_id: UUID
    filename: str


class RelationshipRelatedObject(BaseModel):
    object_type: str
    object_id: UUID
    title: str
    body_excerpt: str | None = None
    review_status: str | None = None
    source_validation_status: str | None = None
    shared_document_count: int
    shared_documents: list[RelationshipRelatedDocument] = Field(default_factory=list)


class RelationshipRelatedByDocumentRequest(BaseModel):
    object_type: str
    object_id: UUID
    max_results: int = Field(default=100, ge=1, le=500)


class RelationshipRelatedByDocumentResponse(BaseModel):
    case_id: UUID
    source_object: RelationshipRelatedSourceObject
    documents: list[RelationshipRelatedDocument] = Field(default_factory=list)
    objects: list[RelationshipRelatedObject] = Field(default_factory=list)


class RelationshipGraph(BaseModel):
    case_id: UUID
    focus_node_id: str
    focus_object_type: str
    focus_object_id: UUID
    focus_node_ids: list[str] = Field(default_factory=list)
    focus_objects: list[RelationshipGraphFocusObject] = Field(default_factory=list)
    nodes: list[RelationshipGraphNode]
    edges: list[RelationshipGraphEdge]
    warnings: list[RelationshipGraphWarning] = Field(default_factory=list)
    limits: RelationshipGraphLimits
