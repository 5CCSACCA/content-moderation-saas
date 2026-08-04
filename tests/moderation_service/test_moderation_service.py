"""
Tests for moderation-service's API contract: auth/RBAC enforcement,
queue filtering logic, action recording, and conflict detection.
The database is an in-memory SQLite instance (see conftest.py) so
tests run instantly without Docker or a real Postgres connection.
"""

# Health
def test_health_endpoint_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# GET /queue — authentication and authorisation
def test_queue_requires_auth(client):
    response = client.get("/queue")
    assert response.status_code == 403


def test_queue_rejects_regular_user_role(client):
    response = client.get(
        "/queue", headers={"Authorization": f"Bearer {client.user_token}"}
    )
    assert response.status_code == 403


def test_queue_accepts_moderator_role(client):
    response = client.get(
        "/queue", headers={"Authorization": f"Bearer {client.moderator_token}"}
    )
    assert response.status_code == 200


def test_queue_accepts_admin_role(client):
    response = client.get(
        "/queue", headers={"Authorization": f"Bearer {client.admin_token}"}
    )
    assert response.status_code == 200


def test_queue_rejects_invalid_token(client):
    response = client.get(
        "/queue", headers={"Authorization": "Bearer not-a-valid-jwt"}
    )
    assert response.status_code == 401



# GET /queue — response shape and filtering logic

def test_queue_returns_only_flagged_submissions(seeded_client):
    response = seeded_client.get(
        "/queue",
        headers={"Authorization": f"Bearer {seeded_client.moderator_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(seeded_client.flagged_sub_id)


def test_queue_response_contains_all_score_fields(seeded_client):
    response = seeded_client.get(
        "/queue",
        headers={"Authorization": f"Bearer {seeded_client.moderator_token}"},
    )
    item = response.json()[0]
    for field in ("toxic", "severe_toxic", "obscene", "threat", "insult", "identity_hate"):
        assert field in item, f"Missing score field: {field}"


def test_queue_excludes_already_actioned_submissions(seeded_client):
    # Action the flagged submission first
    seeded_client.post(
        f"/queue/{seeded_client.flagged_sub_id}/action",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {seeded_client.moderator_token}"},
    )

    response = seeded_client.get(
        "/queue",
        headers={"Authorization": f"Bearer {seeded_client.moderator_token}"},
    )
    assert response.json() == []


def test_queue_is_empty_when_no_flagged_submissions(client):
    response = client.get(
        "/queue", headers={"Authorization": f"Bearer {client.moderator_token}"}
    )
    assert response.status_code == 200
    assert response.json() == []


# POST /queue/{submission_id}/action

def test_action_approve_returns_201(seeded_client):
    response = seeded_client.post(
        f"/queue/{seeded_client.flagged_sub_id}/action",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {seeded_client.moderator_token}"},
    )
    assert response.status_code == 201


def test_action_reject_returns_correct_fields(seeded_client):
    response = seeded_client.post(
        f"/queue/{seeded_client.flagged_sub_id}/action",
        json={"action": "reject", "notes": "clearly abusive"},
        headers={"Authorization": f"Bearer {seeded_client.moderator_token}"},
    )
    body = response.json()
    assert body["action"] == "reject"
    assert body["notes"] == "clearly abusive"
    assert body["submission_id"] == str(seeded_client.flagged_sub_id)
    assert "id" in body
    assert "moderator_id" in body
    assert "created_at" in body


def test_action_ban_user_is_accepted(seeded_client):
    response = seeded_client.post(
        f"/queue/{seeded_client.flagged_sub_id}/action",
        json={"action": "ban_user"},
        headers={"Authorization": f"Bearer {seeded_client.moderator_token}"},
    )
    assert response.status_code == 201
    assert response.json()["action"] == "ban_user"


def test_action_notes_are_optional(seeded_client):
    response = seeded_client.post(
        f"/queue/{seeded_client.flagged_sub_id}/action",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {seeded_client.moderator_token}"},
    )
    assert response.status_code == 201


def test_action_on_nonexistent_submission_returns_404(client):
    import uuid
    response = client.post(
        f"/queue/{uuid.uuid4()}/action",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {client.moderator_token}"},
    )
    assert response.status_code == 404


def test_duplicate_action_on_same_submission_returns_409(seeded_client):
    seeded_client.post(
        f"/queue/{seeded_client.flagged_sub_id}/action",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {seeded_client.moderator_token}"},
    )
    response = seeded_client.post(
        f"/queue/{seeded_client.flagged_sub_id}/action",
        json={"action": "reject"},
        headers={"Authorization": f"Bearer {seeded_client.moderator_token}"},
    )
    assert response.status_code == 409


def test_action_requires_valid_action_type(seeded_client):
    response = seeded_client.post(
        f"/queue/{seeded_client.flagged_sub_id}/action",
        json={"action": "delete"},
        headers={"Authorization": f"Bearer {seeded_client.moderator_token}"},
    )
    assert response.status_code == 422


def test_action_requires_auth(seeded_client):
    response = seeded_client.post(
        f"/queue/{seeded_client.flagged_sub_id}/action",
        json={"action": "approve"},
    )
    assert response.status_code == 403


def test_action_rejects_regular_user_role(seeded_client):
    response = seeded_client.post(
        f"/queue/{seeded_client.flagged_sub_id}/action",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {seeded_client.user_token}"},
    )
    assert response.status_code == 403



# GET /actions — audit trail

def test_actions_returns_empty_list_initially(client):
    response = client.get(
        "/actions", headers={"Authorization": f"Bearer {client.moderator_token}"}
    )
    assert response.status_code == 200
    assert response.json() == []


def test_actions_records_submitted_action(seeded_client):
    seeded_client.post(
        f"/queue/{seeded_client.flagged_sub_id}/action",
        json={"action": "reject", "notes": "spam"},
        headers={"Authorization": f"Bearer {seeded_client.moderator_token}"},
    )
    response = seeded_client.get(
        "/actions",
        headers={"Authorization": f"Bearer {seeded_client.moderator_token}"},
    )
    body = response.json()
    assert len(body) == 1
    assert body[0]["action"] == "reject"
    assert body[0]["notes"] == "spam"


def test_actions_requires_auth(client):
    response = client.get("/actions")
    assert response.status_code == 403


def test_actions_rejects_regular_user_role(client):
    response = client.get(
        "/actions", headers={"Authorization": f"Bearer {client.user_token}"}
    )
    assert response.status_code == 403
