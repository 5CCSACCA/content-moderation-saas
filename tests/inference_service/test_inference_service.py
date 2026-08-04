"""
Tests for inference-service's API contract: request/response shape and
flagging threshold logic. The model itself is mocked (see conftest.py)
so these tests run instantly and don't require downloading real weights
or a working torch/transformers GPU setup — model accuracy is validated
separately during training, not here.
"""
import torch


def test_predict_returns_all_six_label_scores(client):
    response = client.post("/predict", json={"text": "some comment"})
    assert response.status_code == 200
    body = response.json()
    expected_labels = {"toxic", "severe_toxic", "obscene", "threat", "insult", "identity_hate"}
    assert set(body["scores"].keys()) == expected_labels


def test_predict_flags_high_toxicity_score(client):
    # High logit on the "toxic" label (first position) — after sigmoid,
    # this should clear the 0.5 flagging threshold.
    client.fake_model.return_value = type(
        "Output", (), {"logits": torch.tensor([[5.0, -5.0, -5.0, -5.0, -5.0, -5.0]])}
    )()

    response = client.post("/predict", json={"text": "you are terrible"})
    body = response.json()
    assert body["flagged"] is True
    assert body["scores"]["toxic"] > 0.5


def test_predict_does_not_flag_low_toxicity_scores(client):
    # All logits strongly negative — after sigmoid, every score should
    # fall well below the 0.5 flagging threshold.
    client.fake_model.return_value = type(
        "Output", (), {"logits": torch.tensor([[-5.0, -5.0, -5.0, -5.0, -5.0, -5.0]])}
    )()

    response = client.post("/predict", json={"text": "thank you for the help"})
    body = response.json()
    assert body["flagged"] is False
    assert all(score < 0.5 for score in body["scores"].values())


def test_predict_requires_text_field(client):
    response = client.post("/predict", json={})
    assert response.status_code == 422  # FastAPI/Pydantic validation error


def test_health_endpoint_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}