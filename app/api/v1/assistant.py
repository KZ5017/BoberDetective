from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.assistant import (
    AssistantChatCreateRequest,
    AssistantChatDetail,
    AssistantChatList,
    AssistantChatUpdateRequest,
    AssistantMessageRegenerateRequest,
    AssistantMessageSendRequest,
    AssistantMessageSendResponse,
)
from app.services.assistant import (
    AssistantLLMError,
    AssistantNotFoundError,
    AssistantValidationError,
    create_assistant_chat,
    delete_assistant_chat,
    get_assistant_chat,
    list_assistant_chats,
    regenerate_last_assistant_message,
    send_assistant_message,
    update_assistant_chat,
)


router = APIRouter()


@router.get("/assistant/chats", response_model=AssistantChatList)
def get_assistant_chats(db: Session = Depends(get_db)) -> AssistantChatList:
    return AssistantChatList(data=list_assistant_chats(db))


@router.post("/assistant/chats", response_model=AssistantChatDetail, status_code=status.HTTP_201_CREATED)
def post_assistant_chat(payload: AssistantChatCreateRequest, db: Session = Depends(get_db)) -> AssistantChatDetail:
    return create_assistant_chat(db, payload)


@router.get("/assistant/chats/{chat_id}", response_model=AssistantChatDetail)
def get_assistant_chat_detail(chat_id: UUID, db: Session = Depends(get_db)) -> AssistantChatDetail:
    try:
        return get_assistant_chat(db, chat_id)
    except AssistantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/assistant/chats/{chat_id}", response_model=AssistantChatDetail)
def patch_assistant_chat(
    chat_id: UUID,
    payload: AssistantChatUpdateRequest,
    db: Session = Depends(get_db),
) -> AssistantChatDetail:
    try:
        return update_assistant_chat(db, chat_id, payload)
    except AssistantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/assistant/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assistant_chat_endpoint(chat_id: UUID, db: Session = Depends(get_db)) -> None:
    try:
        delete_assistant_chat(db, chat_id)
    except AssistantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return None


@router.post("/assistant/chats/{chat_id}/messages", response_model=AssistantMessageSendResponse)
def post_assistant_message(
    chat_id: UUID,
    payload: AssistantMessageSendRequest,
    db: Session = Depends(get_db),
) -> AssistantMessageSendResponse:
    try:
        return send_assistant_message(db, chat_id, payload)
    except AssistantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AssistantValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AssistantLLMError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/assistant/chats/{chat_id}/messages/regenerate-last", response_model=AssistantMessageSendResponse)
def post_assistant_regenerate_last_message(
    chat_id: UUID,
    payload: AssistantMessageRegenerateRequest,
    db: Session = Depends(get_db),
) -> AssistantMessageSendResponse:
    try:
        return regenerate_last_assistant_message(db, chat_id, payload)
    except AssistantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AssistantValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AssistantLLMError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
