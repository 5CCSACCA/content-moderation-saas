# Content Moderation SaaS

A microservices-based SaaS that automatically screens user comments and messages
for toxic, abusive, or harmful language using a fine-tuned DistilBERT model,
routing flagged content to human moderators for review.

## Architecture

- `gateway` — public entry point, routes requests, validates JWT
- `auth-service` — user registration/login, JWT issuance, role management
- `inference-service` — runs the fine-tuned DistilBERT model
- `submission-service` — accepts and stores user submissions, triggers inference
- `moderation-service` — moderator/admin review queue and override actions
- `worker` — Celery worker for async inference jobs
- `postgres` — relational database (users, submissions, predictions, moderation actions)
- `redis` — message broker for async tasks
- `prometheus` / `grafana` — monitoring and dashboards

See `architecture.md` [or the report] for a full diagram and data flow.

## Project Structure

Each microservice lives in its own folder with an isolated Dockerfile and
`requirements.txt`, so dependencies don't leak between services:

```markdown
gateway/
  Dockerfile
  requirements.txt
  app/
  README.md        <- service-level documentation
auth-service/
  Dockerfile
  requirements.txt
  app/
  README.md
inference-service/
  Dockerfile
  requirements.txt
  app/
  README.md
submission-service/
  ...
moderation-service/
  ...
worker/
  ...
docker-compose.yml
prometheus/
  prometheus.yml
grafana/
  dashboards/
```

Each service's `README.md` documents its purpose, endpoints, and any
service-specific environment variables. 

Every FastAPI service exposes interactive API docs at `/docs` (Swagger UI) and `/redoc` once running, e.g.
`http://localhost:8000/docs`.

## Prerequisites

- Docker and Docker Compose installed
- 4 CPUs / 16GB RAM minimum
- [Any other lab VM requirements]
- No manual `.env` setup, credential entry, or extra steps are required beyond
  the two commands below — all secrets used for local deployment are provided
  with safe defaults in `docker-compose.yml` [adjust if you handle this differently]

## Deployment

Clone the repository, then from the root directory:

```bash
docker compose build
docker compose up
```

This single pair of commands will:
- Build all microservices from their individual Dockerfiles
- Automatically download the fine-tuned DistilBERT model weights during the
  build/startup of `inference-service` [confirm exactly when this happens]
- Start Postgres, Redis, Prometheus, and Grafana alongside the application services
- Run database migrations/table creation on startup [confirm mechanism]

No manual intervention is required. Every service exposes a `/health` endpoint
used by Docker Compose healthchecks to confirm it is responding before being
considered "up."

## Usage

### Register a user
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "..."}'
```

### Log in
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "..."}'
```
**Response:**
```json
{"access_token": "eyJ...", "token_type": "bearer"}
```

### Submit a comment for moderation
```bash
curl -X POST http://localhost:8000/submissions \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{"text": "example comment text"}'
```
**Response:**
```json
{
  "submission_id": 42,
  "flagged": true,
  "scores": {"toxic": 0.87, "threat": 0.02, "insult": 0.65, ...}
}
```

### Review flagged queue (moderator role required)
```bash
curl -X GET http://localhost:8000/moderation/queue \
  -H "Authorization: Bearer eyJ..."
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

- Prometheus scrapes `/metrics` from `gateway`, `inference-service`,
  `submission-service`, and `worker`
- Grafana dashboard available at `http://localhost:3000`
  (default credentials: [fill in])
- Dashboard tracks request rate, inference latency, queue depth, and error
  rate across services

## Development Process

This project follows GitFlow:
- `main` — production-ready, deployable code only (evaluated version)
- `develop` — integration branch
- `feature/*` — individual service/feature development branches
- `release/*` — pre-release stabilisation before merging to `main`

## Testing

```bash
[commands to run the test suite, e.g. pytest across services]
```

Tests cover [unit tests per service + integration test through the gateway —
fill in specifics once written].

## Environment Variables
```
| Variable | Used by | Purpose |
|---|---|---|
| `JWT_SECRET` | auth-service, gateway | Signing key for JWTs |
| `DATABASE_URL` | auth-service, submission-service, moderation-service | Postgres connection string |
| `REDIS_URL` | worker, submission-service | Celery broker connection |
| [add more as needed] | | |

Safe local defaults are set in `docker-compose.yml` for coursework evaluation
purposes; no manual secret configuration is required to deploy.
```