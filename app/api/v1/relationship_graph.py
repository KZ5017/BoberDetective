from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.relationship_graph import RelationshipGraph, RelationshipGraphMultiFocusRequest
from app.services.relationship_graph import (
    RelationshipGraphNotFoundError,
    RelationshipGraphValidationError,
    build_relationship_graph_for_objects,
)

router = APIRouter()


@router.post("/cases/{case_id}/graph/objects", response_model=RelationshipGraph)
def get_relationship_graph_for_objects(
    case_id: UUID,
    request: RelationshipGraphMultiFocusRequest,
    db: Session = Depends(get_db),
) -> RelationshipGraph:
    try:
        return build_relationship_graph_for_objects(
            db,
            case_id=case_id,
            focus_objects=request.focus_objects,
            include_shared_sources=request.include_shared_sources,
            max_nodes=request.max_nodes,
            max_edges=request.max_edges,
        )
    except RelationshipGraphNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RelationshipGraphValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
