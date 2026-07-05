from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DailyIdea, Idea, ValidationReport
from ..schemas.idea import IdeaCreate, IdeaReport, IdeaSummary
from ..services import generation
from .deps import build_report, get_or_404, idea_detail

router = APIRouter()


@router.get("", response_model=list[IdeaSummary])
def list_ideas(
    q: str | None = None,
    category: str | None = None,
    status: str | None = None,
    min_score: float | None = Query(default=None, ge=0, le=100),
    sort: str = Query(default="score", pattern="^(score|newest)$"),
    limit: int = Query(default=25, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Searchable, filterable idea database."""
    query = select(Idea)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(
            Idea.title.ilike(like) | Idea.tagline.ilike(like) | Idea.problem_statement.ilike(like)
        )
    if category:
        query = query.where(Idea.category == category)
    if status:
        query = query.where(Idea.status == status)

    ideas = list(db.scalars(query))
    summaries = []
    for idea in ideas:
        s = IdeaSummary.model_validate(idea)
        report = idea.latest_report
        if report:
            s.overall_score = report.overall_score
            s.verdict = report.verdict
        if min_score is not None and (s.overall_score or 0) < min_score:
            continue
        summaries.append(s)

    if sort == "score":
        summaries.sort(key=lambda s: s.overall_score or 0, reverse=True)
    else:
        summaries.sort(key=lambda s: s.id, reverse=True)
    return summaries[offset : offset + limit]


@router.post("", response_model=IdeaReport, status_code=201)
def submit_idea(payload: IdeaCreate, db: Session = Depends(get_db)):
    """Submit an idea; the platform runs the full analysis stack on intake."""
    idea = Idea(
        slug=generation._unique_slug(db, generation.slugify(payload.title)),
        title=payload.title,
        category=payload.category,
        source="user_submitted",
        problem_statement=payload.problem_statement,
        solution_overview=payload.solution_overview,
        target_audience=payload.target_audience,
        business_model=payload.business_model,
    )
    db.add(idea)
    db.flush()
    generation.analyze_new_idea(db, idea)
    db.commit()
    return build_report(db, idea)


@router.get("/daily", response_model=IdeaReport)
def daily_idea(db: Session = Depends(get_db)):
    """Today's featured idea; auto-selects the best unfeatured idea once per day."""
    today = date.today()
    entry = db.scalar(select(DailyIdea).where(DailyIdea.day == today))
    if entry is None:
        featured_ids = {d.idea_id for d in db.scalars(select(DailyIdea))}
        candidates = db.scalars(
            select(ValidationReport).order_by(ValidationReport.overall_score.desc())
        )
        chosen = next((r.idea for r in candidates if r.idea_id not in featured_ids), None)
        if chosen is None:
            chosen = db.scalar(select(Idea).order_by(Idea.id.desc()))
        if chosen is None:
            raise HTTPException(status_code=404, detail="no ideas in the database yet")
        entry = DailyIdea(day=today, idea_id=chosen.id)
        db.add(entry)
        db.commit()
    return build_report(db, entry.idea)


@router.get("/{slug}", response_model=IdeaReport)
def get_idea(slug: str, db: Session = Depends(get_db)):
    idea = db.scalar(select(Idea).where(Idea.slug == slug))
    if idea is None:
        raise HTTPException(status_code=404, detail=f"idea '{slug}' not found")
    return build_report(db, idea)


@router.post("/{idea_id}/revalidate", response_model=IdeaReport)
def revalidate(idea_id: int, db: Session = Depends(get_db)):
    """Re-run validation + all frameworks (new snapshot, history preserved)."""
    idea = get_or_404(db, Idea, idea_id)
    generation.analyze_new_idea(db, idea)
    db.commit()
    return build_report(db, idea)
