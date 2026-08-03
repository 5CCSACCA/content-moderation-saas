"""Shared pytest fixtures for auth-service tests. uses an in-memory SQLite database instead of Postgres 
so that tests run fast and don't require Docker or a running database.

DATABASE_URL is overidden via environment variable BEFORE importing the app, since auth-service creates 
its SQLAlchemy engine at import time (module level in database.py), and so, patching after import would be too late.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "auth-service"))

# Must be set before any app modules are imported, since database.py
# reads this at module load time to create its engine.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine


@pytest.fixture
def client():
    from app import database, models, main

    # Replace the module's engine with an in-memory SQLite engine using
    # StaticPool, so all connections share the same in-memory database
    # for the duration of the test (plain in-memory SQLite otherwise
    # creates a new empty database per connection).
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