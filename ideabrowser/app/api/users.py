from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Idea, User, UserProfile, WorkspaceItem
from ..schemas.idea import FounderFitOut
from ..schemas.user import (
    ProfileIn,
    ProfileOut,
    UserCreate,
    UserOut,
    WorkspaceItemIn,
    WorkspaceItemOut,
)
from ..services import personalization
from .deps import get_or_404

router = APIRouter()


@router.post("", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status_code=409, detail="email already registered")
    user = User(email=payload.email, name=payload.name, role=payload.role)
    db.add(user)
    db.commit()
    return user


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, User, user_id)


@router.put("/{user_id}/profile", response_model=ProfileOut)
def upsert_profile(user_id: int, payload: ProfileIn, db: Session = Depends(get_db)):
    user = get_or_404(db, User, user_id)
    profile = user.profile or UserProfile(user_id=user.id)
    for field, value in payload.model_dump().items():
        setattr(profile, field, value)
    db.add(profile)
    db.commit()
    return profile


@router.get("/{user_id}/profile", response_model=ProfileOut)
def get_profile(user_id: int, db: Session = Depends(get_db)):
    user = get_or_404(db, User, user_id)
    if user.profile is None:
        raise HTTPException(status_code=404, detail="profile not set")
    return user.profile


@router.get("/{user_id}/recommendations")
def get_recommendations(user_id: int, limit: int = 10, db: Session = Depends(get_db)):
    """Personalized idea ranking: validation quality blended with founder fit."""
    user = get_or_404(db, User, user_id)
    recs = personalization.recommendations(db, user, limit)
    db.commit()
    return recs


@router.get("/{user_id}/founder-fit/{idea_id}", response_model=FounderFitOut)
def get_founder_fit(user_id: int, idea_id: int, db: Session = Depends(get_db)):
    user = get_or_404(db, User, user_id)
    idea = get_or_404(db, Idea, idea_id)
    fit = personalization.founder_fit(db, user, idea)
    db.commit()
    return fit


# ------------------------------------------------------------- workspace
@router.get("/{user_id}/workspace", response_model=list[WorkspaceItemOut])
def list_workspace(user_id: int, db: Session = Depends(get_db)):
    user = get_or_404(db, User, user_id)
    return user.workspace_items


@router.post("/{user_id}/workspace", response_model=WorkspaceItemOut, status_code=201)
def save_idea(user_id: int, payload: WorkspaceItemIn, db: Session = Depends(get_db)):
    user = get_or_404(db, User, user_id)
    get_or_404(db, Idea, payload.idea_id)
    if payload.stage not in WorkspaceItem.STAGES:
        raise HTTPException(status_code=422, detail=f"stage must be one of {WorkspaceItem.STAGES}")
    existing = db.scalar(
        select(WorkspaceItem).where(
            WorkspaceItem.user_id == user.id, WorkspaceItem.idea_id == payload.idea_id
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="idea already in workspace")
    item = WorkspaceItem(user_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    return item


@router.patch("/{user_id}/workspace/{item_id}", response_model=WorkspaceItemOut)
def update_workspace_item(
    user_id: int,
    item_id: int,
    stage: str | None = None,
    notes: str | None = None,
    db: Session = Depends(get_db),
):
    item = get_or_404(db, WorkspaceItem, item_id)
    if item.user_id != user_id:
        raise HTTPException(status_code=403, detail="not your workspace item")
    if stage is not None:
        if stage not in WorkspaceItem.STAGES:
            raise HTTPException(status_code=422, detail=f"stage must be one of {WorkspaceItem.STAGES}")
        item.stage = stage
    if notes is not None:
        item.notes = notes
    db.commit()
    return item
