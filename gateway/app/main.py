import os

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

app = FastAPI(title="Gateway Service", version="0.2.0")

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")
SUBMISSION_SERVICE_URL = os.getenv("SUBMISSION_SERVICE_URL", "http://submission-service:8000")
MODERATION_SERVICE_URL = os.getenv("MODERATION_SERVICE_URL", "http://moderation-service:8000")

# Maps a public path prefix to the internal service that should handle it.
ROUTES = {
    "/auth": AUTH_SERVICE_URL,
    "/submissions": SUBMISSION_SERVICE_URL,
    "/moderation": MODERATION_SERVICE_URL,
}

# moderation-service's own routes don't actually start with "/moderation" —
# they're /queue, /queue/{id}/action, /actions. We strip the "/moderation"
# prefix before forwarding so the internal service sees its real paths.
STRIP_PREFIX = {"/auth", "/moderation"}

client = httpx.AsyncClient(timeout=15.0)


@app.get("/health")
def health():
    """Basic health check endpoint used by Docker Compose healthchecks
    and Prometheus/monitoring to confirm the service is responding."""
    return {"status": "ok"}


@app.get("/")
def root():
    return {"service": "gateway", "message": "Gateway service is running"}


def _resolve_target(path: str):
    """Finds which internal service a given request path should be
    forwarded to, and computes the path to forward as seen by that
    internal service (stripping the gateway-level prefix where needed)."""
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
async def proxy(full_path: str, request: Request):
    """Catch-all reverse proxy. Forwards the incoming request — method,
    headers (including Authorization, so JWTs pass through untouched),
    query params, and body — to whichever internal service owns this
    path, then returns that service's response as-is. Downstream
    services perform their own JWT verification and role checks; the
    gateway's job here is routing, not re-implementing auth logic."""
    path = "/" + full_path
    base_url, forwarded_path = _resolve_target(path)

    if base_url is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"No service is registered to handle path '{path}'"},
        )

    target_url = f"{base_url}{forwarded_path}"

    # Forward all headers except 'host', which must reflect the target,
    # not the original request made to the gateway.
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