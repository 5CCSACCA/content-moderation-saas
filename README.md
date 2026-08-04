# Content Moderation SaaS

A microservices-based SaaS that automatically screens user comments and messages
for toxic, abusive, or harmful language using a fine-tuned DistilBERT model,
routing flagged content to human moderators for review.

**GitHub repository:** https://github.com/5CCSACCA/resit-coursework-moboluw4rin

## Architecture

- `gateway` — sole public entry point; reverse-proxies requests to internal
  services, forwards JWT headers, rate-limits (60 req/min per IP)
- `auth-service` — user registration/login, JWT issuance, role management
  (user / moderator / admin)
- `inference-service` — loads the fine-tuned DistilBERT model, exposes a
  stateless `/predict` endpoint
- `submission-service` — accepts and stores user submissions, enqueues
  asynchronous scoring jobs
- `moderation-service` — role-gated flagged queue, moderator override actions,
  audit trail
- `worker` — Celery worker that consumes scoring jobs, calls inference-service,
  writes predictions to Postgres
- `postgres` — relational database (users, submissions, predictions,
  moderation actions)
- `redis` — Celery broker
- `prometheus` / `grafana` — monitoring and dashboards

A full architecture discussion, including design decisions and diagrams, is
in the accompanying report.

## Project Structure

Each microservice lives in its own folder with an isolated Dockerfile and
`requirements.txt`, so dependencies don't leak between services:

```
gateway/
  Dockerfile
  requirements.txt
  app/
auth-service/
  Dockerfile
  requirements.txt
  app/
inference-service/
  Dockerfile
  requirements.txt
  app/
submission-service/
  Dockerfile
  requirements.txt
  app/
moderation-service/
  Dockerfile
  requirements.txt
  app/
worker/
  Dockerfile
  requirements.txt
  app/
model-training/
  toxicity_distilbert_finetune.ipynb
tests/
  auth_service/
  submission_service/
  inference_service/
  moderation_service/
  integration/
load-test/
  load_test.py
docker-compose.yml
prometheus/
  prometheus.yml
grafana/
  provisioning/
  dashboards/
```

Every FastAPI service exposes interactive API docs at `/docs` (Swagger UI)
once running. Since only `gateway` is publicly exposed, routes are reached
through it (e.g. `http://localhost:8000/auth/register`); individual
services' own `/docs` pages are only reachable from inside the Docker
network in the deployed configuration.

## Prerequisites

- Docker and Docker Compose installed
- 4 CPUs / 16GB RAM minimum

No manual `.env` setup, credential entry, or extra steps are required.
Safe local defaults are provided in `docker-compose.yml` and `.env.example`
for coursework evaluation purposes.

## Deployment

Clone the repository, then from the root directory:

```bash
docker compose up --build
```

This single command will:
- Build all microservices from their individual Dockerfiles
- Automatically download the fine-tuned DistilBERT model weights from
  HuggingFace Hub during the build of `inference-service` (no separate
  download step required)
- Start Postgres, Redis, Prometheus, and Grafana alongside the application
  services
- Create all database tables automatically on first startup
  (`Base.metadata.create_all()` in each service — no manual migration step)

No manual intervention is required. Every service exposes a `/health`
endpoint used by Docker Compose healthchecks; `docker compose ps` shows
`healthy` for every service once the stack is fully up.

## Usage

All requests go through the gateway on port 8000.

### Register a user
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "testpass123"}'
```
**Response:**
```json
{"id": "0749b401-db7c-4014-9666-d0c46067721b", "email": "user@example.com", "role": "user", "created_at": "2026-08-02T20:53:32.071265"}
```

### Log in
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "testpass123"}'
```
**Response:**
```json
{"access_token": "eyJhbGciOiJIUzI1NiIs...", "token_type": "bearer"}
```

### Submit a comment for moderation
```bash
curl -X POST http://localhost:8000/submissions \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"text": "You are an idiot and should shut up."}'
```
**Response** (note: `prediction` is `null` immediately after submission,
since scoring happens asynchronously — poll `GET /submissions/{id}` a
moment later to see the result):
```json
{
  "id": "24580af7-5519-481d-ae59-f69590f8658d",
  "text": "You are an idiot and should shut up.",
  "created_at": "2026-08-03T11:55:53.170862",
  "prediction": null
}
```

### Check a submission's scoring result
```bash
curl http://localhost:8000/submissions/<submission_id> \
  -H "Authorization: Bearer <token>"
```
**Response** (once the worker has processed it):
```json
{
  "id": "24580af7-5519-481d-ae59-f69590f8658d",
  "text": "You are an idiot and should shut up.",
  "created_at": "2026-08-03T11:55:53.170862",
  "prediction": {
    "toxic": 0.9927, "severe_toxic": 0.0782, "obscene": 0.7432,
    "threat": 0.0187, "insult": 0.9485, "identity_hate": 0.0126,
    "flagged": true
  }
}
```

### Review flagged queue (moderator or admin role required)
```bash
curl http://localhost:8000/moderation/queue \
  -H "Authorization: Bearer <moderator_token>"
```

### Submit a moderation decision
```bash
curl -X POST http://localhost:8000/moderation/queue/<submission_id>/action \
  -H "Authorization: Bearer <moderator_token>" \
  -H "Content-Type: application/json" \
  -d '{"action": "reject", "notes": "Confirmed toxic content."}'
```

### View the moderation audit trail
```bash
curl http://localhost:8000/moderation/actions \
  -H "Authorization: Bearer <moderator_token>"
```

### Check service health
```bash
curl http://localhost:8000/health
```
**Response:**
```json
{"status": "ok"}
```

## Monitoring

- Prometheus scrapes `/metrics` from `gateway`, `auth-service`,
  `inference-service`, `submission-service`, and `moderation-service`
  every 15 seconds (accessible at `http://localhost:9090`)
- Grafana dashboard auto-provisioned at `http://localhost:3000`
  (login: `admin` / `admin`)
- Dashboard tracks request rate, p95 latency, and error rate by service,
  plus inference-service request duration and total request volume

## Development Process

This project follows GitFlow:
- `main` — production-ready, deployable code only (the evaluated version)
- `develop` — integration branch
- `feature/*` — individual service/feature development branches
- `release/*` — pre-release stabilisation, merged into both `main` and
  `develop`, then tagged

## Testing

Automated tests are split into fast, isolated unit/API tests per service
(using an in-memory SQLite database and mocked external calls) and a live
integration test that runs against the real, running Docker Compose stack.
The integration test automatically skips itself if the stack isn't running,
so it's safe to include in a single full-suite run regardless.

> **Note**: unit tests for `inference-service` depend on `torch` and
> `transformers`, which require Python 3.11 or 3.12 (Python 3.13 lacks
> prebuilt wheels for `tokenizers`, a `transformers` dependency, and will
> fail to install via pip). This does not affect the deployed system,
> since Docker images use Python 3.11 internally regardless of the host
> machine's Python version — this only affects running the test suite
> directly on your local machine.
>
> If running tests locally on Python 3.13, switch to Python 3.12 via
> pyenv:
> ```bash
> pyenv install 3.12.4          # skip if already installed
> pyenv local 3.12.4            # sets Python 3.12.4 for this directory only
> python -m venv venv
> source venv/bin/activate
> pip install -r tests/requirements-test.txt
> ```
> Alternatively, install Rust to compile `tokenizers` from source instead
> of switching Python versions:
> ```bash
> curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
> source ~/.cargo/env
> pip install -r tests/requirements-test.txt
> ```

**Run the entire test suite in one command:**
```bash
pip install -r tests/requirements-test.txt
pytest tests/ -v
```

**Unit and API-level tests** (no Docker required):
```bash
pip install -r tests/requirements-test.txt
pytest tests/auth_service/ -v
pytest tests/submission_service/ -v
pytest tests/inference_service/ -v
pytest tests/moderation_service/ -v
```

**Integration test** (requires the full stack running via `docker compose up --build` first):
```bash
pytest tests/integration/test_full_pipeline.py -v
```

Coverage includes: password hashing and JWT verification, registration/login
flows, submission creation and async scoring, ownership-based access control,
RBAC enforcement on moderation endpoints, and a full live pipeline test
(register → submit → poll → moderate) through the gateway.

## Load Testing

`load-test/load_test.py` measures latency and throughput through the
gateway at increasing concurrency levels, used to derive the resource
consumption and cost figures discussed in the report's Costs section:

```bash
pip install httpx
python3 load-test/load_test.py
```

## Environment Variables

| Variable | Used by | Purpose |
|---|---|---|
| `JWT_SECRET` | auth-service, submission-service, moderation-service | Signing/verification key for JWTs |
| `DATABASE_URL` | auth-service, submission-service, moderation-service, worker | Postgres connection string |
| `REDIS_URL` | worker, submission-service | Celery broker connection |

Safe local defaults are set in `docker-compose.yml` / `.env.example` for
coursework evaluation purposes; no manual secret configuration is required
to deploy.