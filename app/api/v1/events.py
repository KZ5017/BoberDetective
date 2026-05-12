from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.event import EventDetail, EventList, EventRead, EventSourceRead
from app.services.events import EventNotFoundError, get_event, list_event_sources, list_events

router = APIRouter()


@router.get("/cases/{case_id}/events", response_model=EventList)
def get_case_events(case_id: UUID, db: Session = Depends(get_db)) -> EventList:
    return EventList(data=[EventRead.model_validate(event) for event in list_events(db, case_id)])


@router.get("/cases/{case_id}/events/{event_id}", response_model=EventDetail)
def get_case_event(case_id: UUID, event_id: UUID, db: Session = Depends(get_db)) -> EventDetail:
    try:
        event = get_event(db, case_id, event_id)
    except EventNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return EventDetail(
        event=EventRead.model_validate(event),
        sources=[EventSourceRead.model_validate(source) for source in list_event_sources(db, event_id)],
    )
