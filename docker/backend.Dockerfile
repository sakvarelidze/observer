# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install build dependencies required to compile wheels when prebuilt
# binaries are unavailable for the target architecture.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential python3-dev \
    && python -m venv "$VIRTUAL_ENV" \
    && . "$VIRTUAL_ENV/bin/activate" \
    && pip install --upgrade pip setuptools wheel \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Remove Python bytecode caches that are not required at runtime to help
# keep the layer size small.
RUN find "$VIRTUAL_ENV" -type d -name '__pycache__' -prune -exec rm -rf '{}' + \
    && find "$VIRTUAL_ENV" -type f -name '*.pyc' -delete

FROM gcr.io/distroless/python3-debian12 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY server/ ./server
COPY server/healthcheck.py ./extra/healthcheck.py

EXPOSE 3001
HEALTHCHECK --interval=60s --timeout=30s --retries=5 CMD ["python", "extra/healthcheck.py"]
CMD ["python", "-m", "server.server"]
