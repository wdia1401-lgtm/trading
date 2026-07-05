from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ChatSession, Idea, User
from ..schemas.chat import ChatMessageIn, ChatMessageOut, ChatSessionCreate, ChatSessionOut
from ..services import chat as chat_service
from .deps import get_or_404

router = APIRouter()


@router.post("/sessions", response_model=ChatSessionOut, status_code=201)
def create_session(payload: ChatSessionCreate, db: Session = Depends(get_db)):
    get_or_404(db, User, payload.user_id)
    if payload.idea_id is not None:
        get_or_404(db, Idea, payload.idea_id)
    session = ChatSession(**payload.model_dump())
    db.add(session)
    db.commit()
    return session


@router.get("/sessions/{session_id}", response_model=ChatSessionOut)
def get_session(session_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, ChatSession, session_id)


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageOut, status_code=201)
def send_message(session_id: int, payload: ChatMessageIn, db: Session = Depends(get_db)):
    """Send a user message; returns the AI analyst's grounded reply."""
    session = get_or_404(db, ChatSession, session_id)
    reply = chat_service.send_message(db, session, payload.content)
    db.commit()
    return reply
