import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from .models import ActionType


class FlaggedSubmissionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    text: str
    created_at: datetime
    toxic: float
    severe_toxic: float
    obscene: float
    threat: float
    insult: float
    identity_hate: float

    class Config:
        from_attributes = True


class ModerationActionCreate(BaseModel):
    action: ActionType
    notes: Optional[str] = None


class ModerationActionResponse(BaseModel):
    id: uuid.UUID
    submission_id: uuid.UUID
    moderator_id: uuid.UUID
    action: ActionType
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True