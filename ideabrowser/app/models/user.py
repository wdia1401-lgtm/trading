from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32), default="founder")  # founder | operator | sponsor
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    profile: Mapped["UserProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    workspace_items: Mapped[list["WorkspaceItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserProfile(Base):
    """Founder profile used for personalization and founder-fit scoring."""

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    skills: Mapped[list] = mapped_column(JSON, default=list)        # e.g. ["python", "growth marketing"]
    interests: Mapped[list] = mapped_column(JSON, default=list)     # e.g. ["fintech", "climate"]
    industries: Mapped[list] = mapped_column(JSON, default=list)
    capital_available_usd: Mapped[int] = mapped_column(default=0)
    hours_per_week: Mapped[int] = mapped_column(default=10)
    risk_appetite: Mapped[str] = mapped_column(String(16), default="medium")  # low | medium | high
    goals: Mapped[str] = mapped_column(Text, default="")

    user: Mapped[User] = relationship(back_populates="profile")


class WorkspaceItem(Base):
    """A user's saved idea with progress tracking (kanban-style stages)."""

    __tablename__ = "workspace_items"
    __table_args__ = (UniqueConstraint("user_id", "idea_id", name="uq_workspace_user_idea"),)

    STAGES = ("saved", "researching", "validating", "building", "launched", "abandoned")

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    idea_id: Mapped[int] = mapped_column(ForeignKey("ideas.id"), index=True)
    stage: Mapped[str] = mapped_column(String(24), default="saved")
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped[User] = relationship(back_populates="workspace_items")
    idea = relationship("Idea")
