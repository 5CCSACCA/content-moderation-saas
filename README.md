# Project summary

**MediScreen** is a SaaS platform that turns a CNN-based skin lesion classifier into a clinical screening aid, deployable as a set of Dockerised microservices behind a single REST API.

Clinicians upload dermatological images and receive a prediction (benign/malignant), a confidence score, and a Grad-CAM heatmap showing which region of the image drove the model's decision — supporting interpretability rather than a black-box output. Results below a defined confidence threshold are flagged as inconclusive rather than forced into a binary label, and every output is explicitly framed as a **screening aid, not a diagnostic result**.

The system is built around four core services — authentication, case/results management, model inference, and an API gateway — coordinated via Docker Compose, with Prometheus and Grafana providing runtime monitoring (latency, confidence-score distribution, request volume). Role-based access control (Clinician, Admin, Auditor) is enforced at the API layer, with clinicians restricted to their own cases and a full audit log tracking every access to patient scan data, independent of who can view clinical content itself.

Patient data is pseudonymised at the point of case creation (subject references only, no identifiable information stored), and the model was fine-tuned on the ISIC skin lesion dataset using transfer learning on a MobileNetV2/ResNet backbone, quantized for CPU-only inference.

**Stack:** FastAPI · PyTorch (CPU) · PostgreSQL · Docker Compose · Prometheus · Grafana

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
disease-detection-saas/
├── docker-compose.yml
├── .env.example
├── README.md
│
├── auth-service/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py            # /register, /login, /token
│       ├── models.py          # User, Role, Permission, RolePermission (SQLAlchemy)
│       ├── security.py        # JWT encode/decode, password hashing
│       └── db.py
│
├── inference-service/
│   ├── Dockerfile
│   ├── requirements.txt       # torch (cpu), torchvision, grad-cam, pillow
│   └── app/
│       ├── main.py            # /predict (internal only, service-account scoped)
│       ├── model.py           # loads quantized CNN, runs inference
│       ├── gradcam.py         # heatmap generation
│       └── weights/           # model.pt downloaded at build/up time
│
├── cases-service/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py            # /cases, /cases/{id}/scans — CRUD + RBAC
│       ├── models.py          # Case, ScanResult, AuditLog
│       ├── deps.py            # require_permission(), get_current_user()
│       └── db.py
│
├── gateway/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       └── main.py            # routes to auth/inference/cases, single public entrypoint
│
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/
│       └── dashboards/scan-metrics.json
│
└── shared/
    └── schemas.py             # Pydantic models shared across services (avoid duplication)
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
```
Safe local defaults are set in `docker-compose.yml` for coursework evaluation
purposes; no manual secret configuration is required to deploy.
