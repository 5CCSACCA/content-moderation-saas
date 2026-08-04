import os

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

app = FastAPI(title="Gateway Service", version="0.3.0")

# Rate limiting: identifies clients by IP address and caps requests per
# minute. This is the only publicly exposed service, so it's the right
# place to enforce a global rate limit protecting all downstream
# services from abuse, rather than duplicating this in every service.
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# IMPORTANT: metrics instrumentation must be set up BEFORE the catch-all
# proxy route below is registered. FastAPI/Starlette match routes in
# registration order, and the catch-all matches literally any path —
# including /metrics — so if it were registered first, it would swallow
# Prometheus's scrape requests and return 404 instead of real metrics.
Instrumentator().instrument(app).expose(app)

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")
SUBMISSION_SERVICE_URL = os.getenv("SUBMISSION_SERVICE_URL", "http://submission-service:8000")
MODERATION_SERVICE_URL = os.getenv("MODERATION_SERVICE_URL", "http://moderation-service:8000")

ROUTES = {
    "/auth": AUTH_SERVICE_URL,
    "/submissions": SUBMISSION_SERVICE_URL,
    "/moderation": MODERATION_SERVICE_URL,
}

STRIP_PREFIX = {"/auth", "/moderation"}

client = httpx.AsyncClient(timeout=15.0)


@app.get("/health")
def health():
    """Basic health check endpoint used by Docker Compose healthchecks
    and Prometheus/monitoring to confirm the service is responding.
    Deliberately not rate-limited, since Docker's healthcheck polls
    this frequently and shouldn't be able to trip the limiter."""
    return {"status": "ok"}


@app.get("/")
def root():
    return {"service": "gateway", "message": "Gateway service is running"}


def _resolve_target(path: str):
    for prefix, base_url in ROUTES.items():
        if path == prefix or path.startswith(prefix + "/"):
            if prefix in STRIP_PREFIX:
                forwarded_path = path[len(prefix):] or "/"
            else:
                forwarded_path = path
            return base_url, forwarded_path
    return None, None


@app.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
@limiter.limit("60/minute")
# Temporarily raised to 2000/minute for load testing (see load-test/load_test.py)
# @limiter.limit("2000/minute") 
async def proxy(full_path: str, request: Request):
    """Catch-all reverse proxy, rate-limited to 60 requests per minute
    per client IP. Forwards method, headers (including Authorization),
    query params, and body to whichever internal service owns this
    path. Downstream services still perform their own JWT verification
    and role checks; this is an additional layer, not a replacement."""
    path = "/" + full_path
    base_url, forwarded_path = _resolve_target(path)

    if base_url is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"No service is registered to handle path '{path}'"},
        )

    target_url = f"{base_url}{forwarded_path}"

    forward_headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}

    body = await request.body()

    try:
        response = await client.request(
            method=request.method,
            url=target_url,
            params=request.query_params,
            headers=forward_headers,
            content=body,
        )
    except httpx.HTTPError:
        return JSONResponse(
            status_code=502,
            content={"detail": f"Could not reach upstream service for path '{path}'"},
        )

    excluded_headers = {"content-length", "transfer-encoding", "connection"}
    response_headers = {k: v for k, v in response.headers.items() if k.lower() not in excluded_headers}

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=response_headers,
        media_type=response.headers.get("content-type"),
    )