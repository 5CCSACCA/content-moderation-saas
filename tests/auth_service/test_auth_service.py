"""Unit tests for auth-service. Run with: pytest tests/test_auth_service.py

These test the security module directly (password hashing, JWT creation/verification) 
without needing a running database, plus a couple of API-level tests using FASTAPI's 
TestClient against an in-memory SQLite database for speed and isolation from Postgres.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..","..", "auth-service", "app"))

import pytest


def test_password_hashing_produces_different_hash_each_time():
    from security import hash_password
    hash1 = hash_password("testpass123")
    hash2 = hash_password("testpass123")
    # bcrypt includes a random salt, so identical passwords should
    # never produce identical hashes — this is a security property,
    # not a bug, and worth testing explicitly.
    assert hash1 != hash2


def test_password_verification_succeeds_for_correct_password():
    from security import hash_password, verify_password
    hashed = hash_password("testpass123")
    assert verify_password("testpass123", hashed) is True


def test_password_verification_fails_for_wrong_password():
    from security import hash_password, verify_password
    hashed = hash_password("testpass123")
    assert verify_password("wrongpassword", hashed) is False


def test_jwt_round_trip_preserves_claims():
    from security import create_access_token, decode_access_token
    token = create_access_token(user_id="some-uuid-1234", role="moderator")
    payload = decode_access_token(token)
    assert payload["sub"] == "some-uuid-1234"
    assert payload["role"] == "moderator"


def test_jwt_decode_fails_for_tampered_token():
    from security import create_access_token, decode_access_token
    from jose import JWTError

    token = create_access_token(user_id="some-uuid-1234", role="user")
    tampered = token[:-5] + "aaaaa"  # corrupt the signature

    with pytest.raises(JWTError):
        decode_access_token(tampered)


def test_register_rejects_duplicate_email(client):
    response1 = client.post(
        "/register", json={"email": "dup@example.com", "password": "testpass123"}
    )
    assert response1.status_code == 201

    response2 = client.post(
        "/register", json={"email": "dup@example.com", "password": "testpass123"}
    )
    assert response2.status_code == 409


def test_login_fails_with_wrong_password(client):
    client.post(
        "/register", json={"email": "logintest@example.com", "password": "correctpass123"}
    )
    response = client.post(
        "/login", json={"email": "logintest@example.com", "password": "wrongpass"}
    )
    assert response.status_code == 401


def test_login_succeeds_with_correct_password_and_returns_token(client):
    client.post(
        "/register", json={"email": "logintest2@example.com", "password": "correctpass123"}
    )
    response = client.post(
        "/login", json={"email": "logintest2@example.com", "password": "correctpass123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_me_endpoint_rejects_missing_token(client):
    response = client.get("/me")
    assert response.status_code in (401, 403)  # FastAPI's HTTPBearer returns 403 if header missing entirely