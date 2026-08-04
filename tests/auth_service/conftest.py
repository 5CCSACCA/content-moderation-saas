"""Shared pytest fixtures for auth-service tests. uses an in-memory SQLite database instead of Postgres
so that tests run fast and don't require Docker or a running database.

DATABASE_URL is overidden via environment variable BEFORE importing the app, since auth-service creates
its SQLAlchemy engine at import time (module level in database.py), and so, patching after import would be too late.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

AUTH_SERVICE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "auth-service")


@pytest.fixture
def client():
    # Insert the correct service path at position 0 so that `from app import ...`
    # resolves to auth-service, not whichever service conftest was loaded last.
    sys.path.insert(0, AUTH_SERVICE_PATH)
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

    with TestClient(main.app) as test_client:
        yield test_client

    models.Base.metadata.drop_all(bind=test_engine)

    sys.path.remove(AUTH_SERVICE_PATH)
