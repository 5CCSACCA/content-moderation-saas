FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app

# Download model weights during build so `docker compose up` needs no
# further downloads at runtime, per the coursework requirement that
# missing dependencies are fetched during build or up states.
RUN python -c "from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification; \
    DistilBertTokenizerFast.from_pretrained('moboluw4rin/toxicity-distilbert'); \
    DistilBertForSequenceClassification.from_pretrained('moboluw4rin/toxicity-distilbert')"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]