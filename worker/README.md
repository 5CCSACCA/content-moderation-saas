# Worker

Celery worker that handles asynchronous inference jobs, so submission-service
can respond immediately while scoring happens in the background.

## Tasks
- `ping` — placeholder task confirming the worker is alive and can execute jobs

(Real inference-triggering task to be added, called by submission-service.)

## Environment Variables
- `CELERY_BROKER_URL` — Redis connection string for the task queue (to be added)

## Local run (without Docker)
```bash
pip install -r requirements.txt
celery -A app.main worker --loglevel=info
```