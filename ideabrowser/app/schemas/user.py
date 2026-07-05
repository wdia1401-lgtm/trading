from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .idea import IdeaSummary


class UserCreate(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    name: str = Field(min_length=1, max_length=120)
    role: str = "founder"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: str


class ProfileIn(BaseModel):
    skills: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    capital_available_usd: int = 0
    hours_per_week: int = 10
    risk_appetite: str = "medium"
    goals: str = ""


class ProfileOut(ProfileIn):
    model_config = ConfigDict(from_attributes=True)


class WorkspaceItemIn(BaseModel):
    idea_id: int
    stage: str = "saved"
    notes: str = ""


class WorkspaceItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stage: str
    notes: str
    updated_at: datetime
    idea: IdeaSummary
