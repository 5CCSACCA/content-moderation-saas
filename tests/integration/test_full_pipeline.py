"""
Integration test for the full content moderation pipeline, run against
the real, live Docker Compose stack through the gateway alone — not
mocked, not isolated. This is the closest automated equivalent to the
manual end-to-end testing performed throughout development.

Requires the full stack to be running first:
    docker compose up

Run with:
    pytest tests/integration/test_full_pipeline.py -v

This test is skipped automatically if the gateway isn't reachable,
rather than failing with a confusing connection error — useful so the
rest of the test suite (fast, isolated unit tests) can still run
without Docker, while this one only runs when the full system is up.
"""
import time
import uuid

import httpx
import pytest

BASE_URL = "http://localhost:8000"


def _gateway_is_up() -> bool:
    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=2.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not _gateway_is_up(),
    reason="Gateway is not reachable at localhost:8000 — start the stack with 'docker compose up' first.",
)


def test_full_pipeline_register_submit_flag_moderate():
    """Exercises the complete pipeline through the public gateway only:
    register a new user, log in, submit toxic text, wait for the async
    worker to score it, confirm it's flagged."""

    unique_email = f"integration-test-{uuid.uuid4().hex[:8]}@example.com"
    password = "integrationtestpass123"

    # 1. Register
    register_response = httpx.post(
        f"{BASE_URL}/auth/register",
        json={"email": unique_email, "password": password},
        timeout=10.0,
    )
    assert register_response.status_code == 201, register_response.text

    # 2. Login
    login_response = httpx.post(
        f"{BASE_URL}/auth/login",
        json={"email": unique_email, "password": password},
        timeout=10.0,
    )
    assert login_response.status_code == 200, login_response.text
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Submit toxic text
    submit_response = httpx.post(
        f"{BASE_URL}/submissions",
        json={"text": "You are a disgusting waste of space and should shut up forever."},
        headers=headers,
        timeout=10.0,
    )
    assert submit_response.status_code == 201, submit_response.text
    submission = submit_response.json()
    submission_id = submission["id"]
    assert submission["prediction"] is None

    # 4. Poll until the worker has scored it, with a reasonable timeout
    prediction = None
    for _ in range(20):  # up to ~10 seconds total
        time.sleep(0.5)
        check_response = httpx.get(
            f"{BASE_URL}/submissions/{submission_id}",
            headers=headers,
            timeout=10.0,
        )
        assert check_response.status_code == 200
        prediction = check_response.json()["prediction"]
        if prediction is not None:
            break

    assert prediction is not None, "Worker did not score the submission within the timeout"
    assert prediction["flagged"] is True, "Expected this clearly toxic comment to be flagged"
    assert prediction["toxic"] > 0.5


def test_full_pipeline_rejects_duplicate_registration():
    """Confirms the gateway correctly proxies error responses, not just
    success responses, from auth-service."""
    unique_email = f"integration-dup-{uuid.uuid4().hex[:8]}@example.com"
    password = "integrationtestpass123"

    first = httpx.post(
        f"{BASE_URL}/auth/register",
        json={"email": unique_email, "password": password},
        timeout=10.0,
    )
    assert first.status_code == 201

    second = httpx.post(
        f"{BASE_URL}/auth/register",
        json={"email": unique_email, "password": password},
        timeout=10.0,
    )
    assert second.status_code == 409


def test_full_pipeline_rejects_unauthenticated_submission():
    """Confirms the gateway correctly forwards the Authorization
    requirement through to submission-service, rather than the proxy
    layer accidentally bypassing auth."""
    response = httpx.post(
        f"{BASE_URL}/submissions",
        json={"text": "some comment"},
        timeout=10.0,
    )
    assert response.status_code in (401, 403)