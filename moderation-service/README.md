# Moderation Service

Provides the moderator/admin review queue for flagged submissions, and
endpoints to approve, reject, or override model decisions.

## Endpoints
- `GET /health` — health check
- `GET /` — basic service info

(Review queue, override, and moderator-action endpoints to be added —
role-gated via JWT claims from auth-service.)

## Environment Variables
- `DATABASE_URL` — Postgres connection string (to be added)
- `JWT_SECRET` — shared secret for verifying moderator/admin roles (to be added)

## Local run (without Docker)
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```