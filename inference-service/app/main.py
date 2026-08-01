from fastapi import FastAPI
from pydantic import BaseModel
import torch
from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification

MODEL_NAME = "moboluw4rin/toxicity-distilbert"
MAX_LENGTH = 128
LABEL_COLS = ["toxic", "severe_toxic", "obscene", "threat", "insult", "identity_hate"]

# Threshold below which the highest score is considered too uncertain
# to confidently flag either way — kept simple here, tune later if needed
FLAG_THRESHOLD = 0.5

app = FastAPI(title="Inference Service", version="0.1.0")

# Load model and tokenizer once at startup, not per-request
tokenizer = DistilBertTokenizerFast.from_pretrained(MODEL_NAME)
model = DistilBertForSequenceClassification.from_pretrained(MODEL_NAME)
model.eval()


class PredictRequest(BaseModel):
    text: str


class PredictResponse(BaseModel):
    scores: dict[str, float]
    flagged: bool


@app.get("/health")
def health():
    """Basic health check endpoint used by Docker Compose healthchecks
    and Prometheus/monitoring to confirm the service is responding."""
    return {"status": "ok"}


@app.get("/")
def root():
    return {"service": "inference-service", "message": "Inference service is running"}


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest):
    inputs = tokenizer(
        request.text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=MAX_LENGTH,
    )

    with torch.no_grad():
        logits = model(**inputs).logits

    probs = torch.sigmoid(logits).squeeze().tolist()
    # Ensure probs is always a list even for a single-element output
    if isinstance(probs, float):
        probs = [probs]

    scores = {label: round(score, 4) for label, score in zip(LABEL_COLS, probs)}
    flagged = any(score >= FLAG_THRESHOLD for score in scores.values())

    return PredictResponse(scores=scores, flagged=flagged)
