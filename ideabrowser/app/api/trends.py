from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Trend
from ..schemas.idea import IdeaReport, TrendOut
from ..services import generation, trends as trend_service
from .deps import build_report, get_or_404

router = APIRouter()


@router.get("", response_model=list[TrendOut])
def list_trends(category: str | None = None, db: Session = Depends(get_db)):
    return trend_service.list_trends(db, category)


@router.post("/{trend_id}/refresh", response_model=TrendOut)
def refresh_trend(trend_id: int, db: Session = Depends(get_db)):
    """Recompute momentum/stage from current keyword telemetry."""
    trend = get_or_404(db, Trend, trend_id)
    trend_service.refresh_trend(db, trend)
    db.commit()
    return trend


@router.post("/{trend_id}/generate-idea", response_model=IdeaReport, status_code=201)
def generate_idea(trend_id: int, db: Session = Depends(get_db)):
    """AI-generate one fully analyzed idea seeded by this trend."""
    trend = get_or_404(db, Trend, trend_id)
    idea = generation.generate_from_trend(db, trend)
    db.commit()
    return build_report(db, idea)
