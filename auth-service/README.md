# Auth Service

Handles user registration, login, JWT issuance, and role management.

## Endpoints
- `GET /health` — health check
- `GET /` — basic service info

(Registration, login, and role endpoints to be added.)

## Environment Variables
- `JWT_SECRET` — signing key for JWTs (to be added)
- `DATABASE_URL` — Postgres connection string (to be added)

## Local run (without Docker)
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```