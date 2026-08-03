import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ActionType(str, enum.Enum):
    approve = "approve"     # moderator reviewed and confirmed it's fine, overriding a flag
    reject = "reject"       # moderator confirms the flag was correct, content stays flagged
    ban_user = "ban_user"   # moderator escalates to banning the submitting user


class ModerationAction(Base):
    __tablename__ = "moderation_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    moderator_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    action = Column(Enum(ActionType), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)