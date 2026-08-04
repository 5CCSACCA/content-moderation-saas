"""
Shared pytest fixtures for submission-service tests. Uses an in-memory
SQLite database and mocks the Celery task dispatch, so tests run without
needing Postgres or Redis running.
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

SUBMISSION_SERVICE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "submission-service")

JWT_SECRET = "dev-secret-change-in-production"
JWT_ALGORITHM = "HS256"


def make_token(user_id: str = None, role: str = "user") -> str:
    """Builds a JWT identical in shape to what auth-service would issue,
    without needing auth-service running — submission-service only
    verifies the signature and claims, so this is sufficient for testing
    its authorization logic in isolation."""
    user_id = user_id or str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@pytest.fixture
def client():
    # Insert the correct service path at position 0 so that `from app import ...`
    # resolves to submission-service, not whichever service conftest was loaded last.
    sys.path.insert(0, SUBMISSION_SERVICE_PATH)
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    for key in list(sys.modules.keys()):
        if key == "app" or key.startswith("app."):
            del sys.modules[key]

    from app import database, models, main

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    database.engine = test_engine
    database.SessionLocal.configure(bind=test_engine)
    models.Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = database.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[database.get_db] = override_get_db

    # Mock send_task so tests don't need a running Redis/Celery broker —
    # we're testing submission-service's own logic here, not worker's.
    with patch.object(main.celery_app, "send_task", return_value=None) as mock_send_task:
        with TestClient(main.app) as test_client:
            test_client.mock_send_task = mock_send_task
            yield test_client

    models.Base.metadata.drop_all(bind=test_engine)

    sys.path.remove(SUBMISSION_SERVICE_PATH)
