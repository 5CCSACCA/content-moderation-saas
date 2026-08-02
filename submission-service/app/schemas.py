import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SubmissionCreate(BaseModel):
    text: str


class PredictionResponse(BaseModel):
    toxic: float
    severe_toxic: float
    obscene: float
    threat: float
    insult: float
    identity_hate: float
    flagged: bool

    class Config:
        from_attributes = True


class SubmissionResponse(BaseModel):
    id: uuid.UUID
    text: str
    created_at: datetime
    prediction: Optional[PredictionResponse] = None

    class Config:
        from_attributes = True