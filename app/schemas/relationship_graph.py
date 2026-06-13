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
    focus_objects: list[RelationshipGraphFocusObject] = Field(min_length=1, max_length=20)
    include_shared_sources: bool = True
    max_nodes: int = Field(default=150, ge=1, le=200)
    max_edges: int = Field(default=250, ge=1, le=350)


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
