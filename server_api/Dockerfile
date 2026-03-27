FROM python:3.12-slim AS stage1_legacy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]


FROM stage1_legacy AS stage2

ENV TESSERACT_CMD=/usr/bin/tesseract \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata \
    LLM_KNOWLEDGE_PATH=/app/knowledge_base

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-kor \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]


FROM stage2 AS final
