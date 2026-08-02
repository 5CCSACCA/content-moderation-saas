import os
import uuid

import httpx
from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Prediction, Submission
from .schemas import SubmissionCreate, SubmissionResponse
from .security import CurrentUser, get_current_user

app = FastAPI(title="Submission Service", version="0.1.0")

Base.metadata.create_all(bind=engine)

INFERENCE_SERVICE_URL = os.getenv("INFERENCE_SERVICE_URL", "http://inference-service:8000")


@app.get("/health")
def health():
    """Basic health check endpoint used by Docker Compose healthchecks
    and Prometheus/monitoring to confirm the service is responding."""
    return {"status": "ok"}


@app.get("/")
def root():
    return {"service": "submission-service", "message": "Submission service is running"}


@app.post("/submissions", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
def create_submission(
    payload: SubmissionCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accepts a comment from an authenticated user, sends it to
    inference-service for scoring, and stores both the submission and
    its prediction. Any authenticated user can submit — moderation
    endpoints (separate service) are what's role-gated, not this one."""

    submission = Submission(
        user_id=uuid.UUID(current_user.user_id),
        text=payload.text,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    try:
        response = httpx.post(
            f"{INFERENCE_SERVICE_URL}/predict",
            json={"text": payload.text},
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        # The submission itself is still saved even if scoring fails —
        # this avoids losing user data due to a transient downstream
        # issue, and the missing prediction is visible to the caller.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Submission saved, but inference-service could not be reached",
        )

    result = response.json()
    scores = result["scores"]

    prediction = Prediction(
        submission_id=submission.id,
        toxic=scores["toxic"],
        severe_toxic=scores["severe_toxic"],
        obscene=scores["obscene"],
        threat=scores["threat"],
        insult=scores["insult"],
        identity_hate=scores["identity_hate"],
        flagged=result["flagged"],
        raw_scores=scores,
    )
    db.add(prediction)
    db.commit()
    db.refresh(submission)  # refresh to pick up the new prediction relationship

    return submission


@app.get("/submissions/{submission_id}", response_model=SubmissionResponse)
def get_submission(
    submission_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Users can only view their own submissions — moderators/admins
    use the separate moderation-service to view the flagged queue
    across all users."""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()

    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    if str(submission.user_id) != current_user.user_id and current_user.role not in ("moderator", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this submission")

    return submission