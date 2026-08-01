from fastapi import FastAPI

app = FastAPI(title="Moderation Service", version="0.1.0")


@app.get("/health")
def health():
    """Basic health check endpoint used by Docker Compose healthchecks
    and Prometheus/monitoring to confirm the service is responding."""
    return {"status": "ok"}


@app.get("/")
def root():
    return {"service": "moderation-service", "message": "Moderation service is running"}