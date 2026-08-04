import uuid

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, ProgrammingError

from .database import get_db, engine
from .models import Base as ActionsBase, ModerationAction
from .shared_models import Prediction, Submission
from .schemas import (
    FlaggedSubmissionResponse,
    ModerationActionCreate,
    ModerationActionResponse,
)
from .security import CurrentUser, require_moderator

app = FastAPI(title="Moderation Service", version="0.1.0")

from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)

# Only create moderation_actions here — submissions/predictions are owned
# and created by submission-service; this service only reads them.
try:
    ActionsBase.metadata.create_all(bind=engine)
except (IntegrityError, ProgrammingError):
    pass


@app.get("/health")
def health():
    """Basic health check endpoint used by Docker Compose healthchecks
    and Prometheus/monitoring to confirm the service is responding."""
    return {"status": "ok"}


@app.get("/")
def root():
    return {"service": "moderation-service", "message": "Moderation service is running"}


@app.get("/queue", response_model=list[FlaggedSubmissionResponse])
def get_flagged_queue(
    current_user: CurrentUser = Depends(require_moderator),
    db: Session = Depends(get_db),
):
    """Returns all flagged submissions that haven't yet received a
    moderation action, ordered oldest-first so moderators work through
    the backlog in order. Moderator/admin role required."""
    already_actioned_ids = {row.submission_id for row in db.query(ModerationAction.submission_id).all()}

    flagged = (
        db.query(Submission)
        .join(Prediction)
        .filter(Prediction.flagged == True)  # noqa: E712
        .order_by(Submission.created_at.asc())
        .all()
    )

    pending = [s for s in flagged if s.id not in already_actioned_ids]

    return [
        FlaggedSubmissionResponse(
            id=s.id,
            user_id=s.user_id,
            text=s.text,
            created_at=s.created_at,
            toxic=s.prediction.toxic,
            severe_toxic=s.prediction.severe_toxic,
            obscene=s.prediction.obscene,
            threat=s.prediction.threat,
            insult=s.prediction.insult,
            identity_hate=s.prediction.identity_hate,
        )
        for s in pending
    ]


@app.post(
    "/queue/{submission_id}/action",
    response_model=ModerationActionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_moderation_action(
    submission_id: uuid.UUID,
    payload: ModerationActionCreate,
    current_user: CurrentUser = Depends(require_moderator),
    db: Session = Depends(get_db),
):
    """Records a moderator's decision on a flagged submission — approve
    (overrides the model's flag), reject (confirms it), or ban_user
    (escalates). Moderator/admin role required."""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    existing = db.query(ModerationAction).filter(ModerationAction.submission_id == submission_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This submission has already been actioned",
        )

    action = ModerationAction(
        submission_id=submission_id,
        moderator_id=uuid.UUID(current_user.user_id),
        action=payload.action,
        notes=payload.notes,
    )
    db.add(action)
    db.commit()
    db.refresh(action)

    return action


@app.get("/actions", response_model=list[ModerationActionResponse])
def get_all_actions(
    current_user: CurrentUser = Depends(require_moderator),
    db: Session = Depends(get_db),
):
    """Full audit trail of every moderation decision made — supports
    the report's discussion of accountability and oversight."""
    return db.query(ModerationAction).order_by(ModerationAction.created_at.desc()).all()