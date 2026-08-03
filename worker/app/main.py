import os
import uuid

import httpx
from celery import Celery

from .database import SessionLocal
from .models import Prediction, Submission

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
INFERENCE_SERVICE_URL = os.getenv("INFERENCE_SERVICE_URL", "http://inference-service:8000")

app = Celery("worker", broker=REDIS_URL, backend=REDIS_URL)


@app.task(name="score_submission", bind=True, max_retries=3, default_retry_delay=5)
def score_submission(self, submission_id: str):
    """Fetches the submission's text, sends it to inference-service for
    scoring, and writes the resulting prediction to Postgres. Runs
    asynchronously so submission-service can respond immediately after
    saving the submission, rather than blocking on inference-service's
    response time.

    Retries up to 3 times with a 5-second delay if inference-service is
    temporarily unreachable, before giving up and leaving the submission
    unscored (visible to the caller as a submission with prediction=null).
    """
    db = SessionLocal()
    try:
        submission = db.query(Submission).filter(Submission.id == uuid.UUID(submission_id)).first()
        if not submission:
            return {"status": "error", "detail": "Submission not found"}

        try:
            response = httpx.post(
                f"{INFERENCE_SERVICE_URL}/predict",
                json={"text": submission.text},
                timeout=10.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise self.retry(exc=exc)

        result = response.json()
        scores = result["scores"]

        existing = db.query(Prediction).filter(Prediction.submission_id == submission.id).first()
        if existing:
            return {"status": "already_scored"}

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

        return {"status": "scored", "flagged": result["flagged"]}
    finally:
        db.close()