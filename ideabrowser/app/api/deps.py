from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Idea, IdeaTrend
from ..schemas.idea import (
    CompetitorOut,
    FrameworkAssessmentOut,
    IdeaDetail,
    IdeaReport,
    KeywordOut,
    SignalOut,
    TrendOut,
    ValidationReportOut,
)


def get_or_404(db: Session, model, obj_id: int, label: str | None = None):
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{label or model.__name__} {obj_id} not found")
    return obj


def idea_detail(idea: Idea) -> IdeaDetail:
    detail = IdeaDetail.model_validate(idea)
    report = idea.latest_report
    if report:
        detail.overall_score = report.overall_score
        detail.verdict = report.verdict
    return detail


def build_report(db: Session, idea: Idea) -> IdeaReport:
    """Assemble the full interactive report payload for one idea."""
    trends = [
        TrendOut.model_validate(it.trend)
        for it in db.scalars(select(IdeaTrend).where(IdeaTrend.idea_id == idea.id))
    ]
    report = idea.latest_report
    return IdeaReport(
        idea=idea_detail(idea),
        validation=ValidationReportOut.model_validate(report) if report else None,
        frameworks=[FrameworkAssessmentOut.model_validate(f) for f in idea.framework_assessments],
        keywords=[KeywordOut.model_validate(ik.keyword) for ik in idea.keywords],
        signals=[SignalOut.model_validate(s) for s in idea.signals],
        competitors=[CompetitorOut.model_validate(c) for c in idea.competitors],
        trends=trends,
    )
