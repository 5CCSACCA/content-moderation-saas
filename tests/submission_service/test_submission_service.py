"""
Tests for submission-service, focusing on authentication enforcement
and ownership-based access control.
"""
from conftest import make_token


def test_create_submission_requires_authentication(client):
    response = client.post("/submissions", json={"text": "some comment"})
    assert response.status_code in (401, 403)


def test_create_submission_succeeds_with_valid_token(client):
    token = make_token(role="user")
    response = client.post(
        "/submissions",
        json={"text": "some comment"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["prediction"] is None
    assert body["text"] == "some comment"


def test_create_submission_enqueues_scoring_task(client):
    token = make_token(role="user")
    client.post(
        "/submissions",
        json={"text": "some comment"},
        headers={"Authorization": f"Bearer {token}"},
    )
    client.mock_send_task.assert_called_once()
    call_args = client.mock_send_task.call_args
    assert call_args.args[0] == "score_submission"


def test_owner_can_view_their_own_submission(client):
    owner_id = "11111111-1111-1111-1111-111111111111"
    token = make_token(user_id=owner_id, role="user")
    create_response = client.post(
        "/submissions",
        json={"text": "some comment"},
        headers={"Authorization": f"Bearer {token}"},
    )
    submission_id = create_response.json()["id"]

    get_response = client.get(
        f"/submissions/{submission_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200


def test_other_regular_user_cannot_view_someone_elses_submission(client):
    owner_id = "11111111-1111-1111-1111-111111111111"
    other_id = "22222222-2222-2222-2222-222222222222"

    owner_token = make_token(user_id=owner_id, role="user")
    create_response = client.post(
        "/submissions",
        json={"text": "some comment"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    submission_id = create_response.json()["id"]

    other_token = make_token(user_id=other_id, role="user")
    get_response = client.get(
        f"/submissions/{submission_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert get_response.status_code == 403


def test_moderator_can_view_any_users_submission(client):
    owner_id = "11111111-1111-1111-1111-111111111111"
    moderator_id = "33333333-3333-3333-3333-333333333333"

    owner_token = make_token(user_id=owner_id, role="user")
    create_response = client.post(
        "/submissions",
        json={"text": "some comment"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    submission_id = create_response.json()["id"]

    moderator_token = make_token(user_id=moderator_id, role="moderator")
    get_response = client.get(
        f"/submissions/{submission_id}",
        headers={"Authorization": f"Bearer {moderator_token}"},
    )
    assert get_response.status_code == 200


def test_get_nonexistent_submission_returns_404(client):
    token = make_token(role="user")
    response = client.get(
        "/submissions/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_create_submission_rejects_empty_text(client):
    token = make_token(role="user")
    response = client.post(
        "/submissions",
        json={"text": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_create_submission_rejects_whitespace_only_text(client):
    token = make_token(role="user")
    response = client.post(
        "/submissions",
        json={"text": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422