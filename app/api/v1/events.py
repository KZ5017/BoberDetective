from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.event import EventDetail, EventList, EventRead, EventSourceRead
from app.schemas.review import HumanReviewCreate, HumanReviewRead
from app.services.events import EventError, EventNotFoundError, get_event, list_event_reviews, list_event_sources, list_events, review_event

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
        reviews=[HumanReviewRead.model_validate(review) for review in list_event_reviews(db, event_id)],
    )


@router.post("/cases/{case_id}/events/{event_id}/reviews", response_model=EventDetail)
def post_event_review(
    case_id: UUID,
    event_id: UUID,
    payload: HumanReviewCreate,
    db: Session = Depends(get_db),
) -> EventDetail:
    try:
        event = review_event(
            db,
            case_id=case_id,
            event_id=event_id,
            action_type=payload.action_type,
            review_comment=payload.review_comment,
        )
    except EventNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EventError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return EventDetail(
        event=EventRead.model_validate(event),
        sources=[EventSourceRead.model_validate(source) for source in list_event_sources(db, event_id)],
        reviews=[HumanReviewRead.model_validate(review) for review in list_event_reviews(db, event_id)],
    )
