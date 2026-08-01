# Submission Service

Accepts user-submitted comments, sends them to inference-service for
scoring, and stores the submission and its prediction results.

## Endpoints
- `GET /health` — health check
- `GET /` — basic service info

(Submission creation, storage, and inference-triggering endpoints to be added.)

## Environment Variables
- `DATABASE_URL` — Postgres connection string (to be added)
- `INFERENCE_SERVICE_URL` — internal address of inference-service (to be added)

## Local run (without Docker)
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```