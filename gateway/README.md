# Gateway Service

Public entry point for the SaaS. Routes requests to internal microservices
and validates JWTs before forwarding.

## Endpoints
- `GET /health` — health check
- `GET /` — basic service info

## Environment Variables
- `JWT_SECRET` — shared secret for verifying tokens (to be added)

## Local run (without Docker)
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```