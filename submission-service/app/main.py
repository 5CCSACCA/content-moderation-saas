import os
import uuid

from celery import Celery
from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Submission
from .schemas import SubmissionCreate, SubmissionResponse
from .security import CurrentUser, get_current_user

app = FastAPI(title="Submission Service", version="0.2.0")

Base.metadata.create_all(bind=engine)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Connects to the same Celery broker as worker, referencing the task by
# name only — submission-service doesn't need to import worker's code,
# just needs to know the name of the task and where the broker lives.
celery_app = Celery("submission-service", broker=REDIS_URL, backend=REDIS_URL)


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
    """Accepts a comment from an authenticated user, saves it immediately,
    and enqueues an asynchronous scoring job rather than calling
    inference-service directly. The response returns right away with
    prediction=null; the client can poll GET /submissions/{id} to see
    the result once worker has processed the job."""

    submission = Submission(
        user_id=uuid.UUID(current_user.user_id),
        text=payload.text,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    celery_app.send_task("score_submission", args=[str(submission.id)])

    return submission


@app.get("/submissions/{submission_id}", response_model=SubmissionResponse)
def get_submission(
    submission_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Users can only view their own submissions — moderators/admins
    use the separate moderation-service to view the flagged queue
    across all users. If prediction is still null, worker hasn't
    finished scoring it yet — the client should poll again shortly."""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()

    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    if str(submission.user_id) != current_user.user_id and current_user.role not in ("moderator", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this submission")

    return submission