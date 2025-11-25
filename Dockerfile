# syntax=docker/dockerfile:1

FROM python:3.11-slim AS builder
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt
COPY . /app

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src
COPY --from=builder /install /usr/local
COPY . /app
EXPOSE 8000
ENV UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000 \
    UVICORN_WORKERS=2 \
    UVICORN_TIMEOUT=65
CMD ["sh", "-c", "uvicorn api.main:app --host ${UVICORN_HOST} --port ${UVICORN_PORT} --workers ${UVICORN_WORKERS} --timeout-keep-alive ${UVICORN_TIMEOUT}"]
