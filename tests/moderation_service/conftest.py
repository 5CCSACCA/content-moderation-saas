"""
Shared pytest fixtures for moderation-service tests. Uses an in-memory
SQLite database instead of Postgres so tests run without Docker or a
running database. JWT tokens are generated with the same dev secret the
service reads from the environment, letting us test real auth behaviour.

DATABASE_URL is overridden via environment variable BEFORE importing the
app because moderation-service creates its SQLAlchemy engine at module
level in database.py — patching after import would be too late.
"""
import os
import sys
import uuid

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

MODERATION_SERVICE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "moderation-service"
)

JWT_SECRET = "dev-secret-change-in-production"
JWT_ALGORITHM = "HS256"


# SQLite doesn't understand PostgreSQL-specific column types. Patch them
# before any app module is imported so model definitions pick up the
# SQLite-compatible versions instead of failing at create_all time.
import json as _json
import sqlalchemy.dialects.postgresql as _pg
from sqlalchemy import types as _sat


class _SQLiteUUID(_sat.TypeDecorator):
    impl = _sat.String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return uuid.UUID(value) if value is not None else None


class _SQLiteJSONB(_sat.TypeDecorator):
    impl = _sat.Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return _json.dumps(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return _json.loads(value) if value is not None else None


_pg.UUID = _SQLiteUUID
_pg.JSONB = _SQLiteJSONB


def make_token(role: str = "moderator", user_id: str | None = None) -> str:
    payload = {"sub": user_id or str(uuid.uuid4()), "role": role}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@pytest.fixture
def client():
    sys.path.insert(0, MODERATION_SERVICE_PATH)
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    for key in list(sys.modules.keys()):
        if key == "app" or key.startswith("app."):
            del sys.modules[key]

    from app import database, models, shared_models, main

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    database.engine = test_engine
    database.SessionLocal.configure(bind=test_engine)

    # Create all tables — both moderation_actions (owned here) and the
    # shared submissions/predictions tables (owned by submission-service
    # but mirrored here as read-only; we create them so tests can seed data).
    models.Base.metadata.create_all(bind=test_engine)
    shared_models.Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = database.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[database.get_db] = override_get_db

    with TestClient(main.app) as test_client:
        test_client.moderator_token = make_token(role="moderator")
        test_client.admin_token = make_token(role="admin")
        test_client.user_token = make_token(role="user")
        test_client.db_engine = test_engine
        yield test_client

    models.Base.metadata.drop_all(bind=test_engine)
    shared_models.Base.metadata.drop_all(bind=test_engine)

    sys.path.remove(MODERATION_SERVICE_PATH)


@pytest.fixture
def seeded_client(client):
    """Client with one flagged and one unflagged submission pre-seeded."""
    from sqlalchemy.orm import sessionmaker
    from app.shared_models import Submission, Prediction

    Session = sessionmaker(bind=client.db_engine)
    db = Session()

    flagged_sub_id = uuid.uuid4()
    unflagged_sub_id = uuid.uuid4()
    user_id = uuid.uuid4()

    db.add(Submission(id=flagged_sub_id, user_id=user_id, text="you are terrible"))
    db.add(Submission(id=unflagged_sub_id, user_id=user_id, text="thank you for your help"))
    db.add(Prediction(
        submission_id=flagged_sub_id,
        toxic=0.92, severe_toxic=0.1, obscene=0.05,
        threat=0.02, insult=0.15, identity_hate=0.01,
        flagged=True,
    ))
    db.add(Prediction(
        submission_id=unflagged_sub_id,
        toxic=0.03, severe_toxic=0.01, obscene=0.01,
        threat=0.01, insult=0.02, identity_hate=0.01,
        flagged=False,
    ))
    db.commit()
    db.close()

    client.flagged_sub_id = flagged_sub_id
    client.unflagged_sub_id = unflagged_sub_id
    client.user_id = user_id
    return client
