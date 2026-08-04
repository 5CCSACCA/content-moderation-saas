"""
Shared pytest fixtures for inference-service tests. Mocks the DistilBERT
tokenizer and model at import time, so tests run instantly without
downloading real model weights from HuggingFace or needing torch to
actually run inference — this tests the API contract (request/response
shape, threshold logic) rather than the model's actual accuracy, which
is evaluated separately during training (see the Colab notebook).
"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "inference-service"))

import pytest
import torch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    fake_tokenizer_instance = MagicMock()
    # A minimal fake tokenizer output — real tokenizer output is a dict-like
    # BatchEncoding; the model only needs it to be unpackable as **kwargs.
    fake_tokenizer_instance.return_value = {"input_ids": torch.tensor([[101, 102]])}

    fake_model_instance = MagicMock()

    sys.modules.pop("app", None)
    sys.modules.pop("app.main", None)

    with patch(
        "transformers.DistilBertTokenizerFast.from_pretrained",
        return_value=fake_tokenizer_instance,
    ), patch(
        "transformers.DistilBertForSequenceClassification.from_pretrained",
        return_value=fake_model_instance,
    ):
        from app import main

        # Default: moderate-toxic-looking output. Individual tests override
        # this via the fixture's returned mock model when they need a
        # specific score pattern (e.g. to test the flagging threshold).
        fake_logits = torch.tensor([[2.0, -3.0, -3.0, -3.0, -3.0, -3.0]])
        fake_model_instance.return_value = type("Output", (), {"logits": fake_logits})()

        main.tokenizer = fake_tokenizer_instance
        main.model = fake_model_instance

        with TestClient(main.app) as test_client:
            test_client.fake_model = fake_model_instance
            yield test_client