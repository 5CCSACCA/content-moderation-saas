# Model Training

This notebook documents the fine-tuning process for the DistilBERT toxicity
classifier used by `inference-service`. It was run in Google Colab (A100 GPU)
and the resulting model was pushed to HuggingFace Hub at
[moboluw4rin/toxicity-distilbert](https://huggingface.co/moboluw4rin/toxicity-distilbert),
from which `inference-service` downloads it automatically during Docker build.

**Dataset**: Jigsaw Toxic Comment Classification Challenge (Kaggle)
**Approach**: fine-tuned only the final transformer layer and classification
head, keeping the rest of DistilBERT's pretrained weights frozen.