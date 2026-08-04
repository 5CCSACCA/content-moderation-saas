"""
Unit tests for the input validation added to auth-service: password
complexity requirements (minimum length, must contain both a letter
and a digit) and email normalization (case-insensitive storage and
matching), including registration, login, and duplicate-detection
behaviour under different casing.
"""

def test_register_rejects_password_with_only_letters(client):
    response = client.post(
        "/register", json={"email": "onlyletters@example.com", "password": "onlyletters"}
    )
    assert response.status_code == 422


def test_register_rejects_password_with_only_digits(client):
    response = client.post(
        "/register", json={"email": "onlydigits@example.com", "password": "12345678"}
    )
    assert response.status_code == 422


def test_register_accepts_password_with_letters_and_digits(client):
    response = client.post(
        "/register", json={"email": "validpass@example.com", "password": "testpass123"}
    )
    assert response.status_code == 201


def test_register_rejects_password_shorter_than_8_chars(client):
    response = client.post(
        "/register", json={"email": "shortpass@example.com", "password": "abc123"}
    )
    assert response.status_code == 422


def test_register_normalizes_email_to_lowercase(client):
    response = client.post(
        "/register", json={"email": "MixedCase@Example.COM", "password": "testpass123"}
    )
    assert response.status_code == 201
    assert response.json()["email"] == "mixedcase@example.com"


def test_login_matches_email_regardless_of_casing(client):
    client.post(
        "/register", json={"email": "casetest@example.com", "password": "testpass123"}
    )
    response = client.post(
        "/login", json={"email": "CaseTest@EXAMPLE.com", "password": "testpass123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_duplicate_registration_detected_regardless_of_casing(client):
    client.post(
        "/register", json={"email": "dupcase@example.com", "password": "testpass123"}
    )
    response = client.post(
        "/register", json={"email": "DupCase@Example.com", "password": "testpass123"}
    )
    assert response.status_code == 409