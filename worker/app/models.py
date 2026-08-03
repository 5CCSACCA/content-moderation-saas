import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Text, Float, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# Mirrors submission-service's table definitions exactly, since both
# services share the same Postgres database. worker only ever reads
# Submission rows and writes Prediction rows — it never creates or
# migrates these tables; submission-service remains the schema owner.


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    prediction = relationship("Prediction", back_populates="submission", uselist=False)


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("submissions.id"), nullable=False, unique=True)

    toxic = Column(Float, nullable=False)
    severe_toxic = Column(Float, nullable=False)
    obscene = Column(Float, nullable=False)
    threat = Column(Float, nullable=False)
    insult = Column(Float, nullable=False)
    identity_hate = Column(Float, nullable=False)

    flagged = Column(Boolean, nullable=False, default=False)
    raw_scores = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    submission = relationship("Submission", back_populates="prediction")