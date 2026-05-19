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

# Don't carry the venv's /opt/venv/bin shims into the runtime — those are
# symlinks back to python:3.11-slim's /usr/local/bin/python3.11 path, which
# doesn't exist in distroless (it ships /usr/bin/python3.11). PYTHONPATH
# lets distroless's own interpreter pick up the installed site-packages
# directly, no venv reactivation required.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/venv/lib/python3.11/site-packages

WORKDIR /app

COPY --from=builder /opt/venv/lib/python3.11/site-packages /opt/venv/lib/python3.11/site-packages
COPY server/ ./server
COPY server/healthcheck.py ./extra/healthcheck.py

EXPOSE 3001
# Distroless's default ENTRYPOINT is /usr/bin/python3.11, so CMD provides
# the interpreter args. HEALTHCHECK's CMD bypasses ENTRYPOINT, so the
# interpreter has to be named explicitly.
HEALTHCHECK --interval=60s --timeout=30s --retries=5 CMD ["/usr/bin/python3.11", "extra/healthcheck.py"]
CMD ["-m", "server.server"]
