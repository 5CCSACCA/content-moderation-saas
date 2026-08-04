import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class SubmissionCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, v):
        if not v.strip():
            raise ValueError("text cannot be empty or whitespace only")
        return v

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