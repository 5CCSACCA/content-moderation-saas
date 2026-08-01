# Inference Service

Loads the fine-tuned DistilBERT toxicity classifier
([moboluw4rin/toxicity-distilbert](https://huggingface.co/moboluw4rin/toxicity-distilbert))
and exposes a prediction endpoint scoring text across six toxicity categories.

## Endpoints
- `GET /health` — health check
- `GET /` — basic service info
- `POST /predict` — classify text for toxicity

### Example request
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "You are an idiot and should shut up."}'
```

### Example response
```json
{
  "scores": {
    "toxic": 0.91,
    "severe_toxic": 0.12,
    "obscene": 0.34,
    "threat": 0.01,
    "insult": 0.87,
    "identity_hate": 0.02
  },
  "flagged": true
}
```

## Model
Fine-tuned DistilBERT (`distilbert-base-uncased` backbone), only the final
transformer layer and classification head were unfrozen during training.
Model weights are downloaded automatically during `docker build` from
HuggingFace Hub — no manual download step required.

## Local run (without Docker)
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```