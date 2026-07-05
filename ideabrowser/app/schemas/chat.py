from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatSessionCreate(BaseModel):
    user_id: int
    idea_id: int | None = None
    title: str = "New conversation"


class ChatMessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    created_at: datetime


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    idea_id: int | None
    title: str
    messages: list[ChatMessageOut] = []
