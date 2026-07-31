# Inference Service

Loads the fine-tuned DistilBERT model and exposes a prediction endpoint
for scoring text across toxicity categories (toxic, severe_toxic, obscene,
threat, insult, identity_hate).

## Endpoints
- `GET /health` — health check
- `GET /` — basic service info

(Model loading and `/predict` endpoint to be added.)

## Environment Variables
- `MODEL_PATH` — location of the fine-tuned model weights (to be added)

## Local run (without Docker)
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```