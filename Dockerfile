# =============================================================================
# Production Multi-Stage Dockerfile for FreshDash (Django + SQLite3 + WhiteNoise)
# =============================================================================

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# Final runtime image
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/freshdash/.local/bin:$PATH" \
    SQLITE_DB_PATH="/data/db.sqlite3" \
    MEDIA_ROOT="/data/media"

# Create non-root user and persistent directories
RUN useradd -u 1000 -m -s /bin/bash freshdash \
    && mkdir -p /app /data /data/media /app/staticfiles /app/logs \
    && chown -R freshdash:freshdash /app /data

WORKDIR /app

COPY --from=builder --chown=freshdash:freshdash /root/.local /home/freshdash/.local
COPY --chown=freshdash:freshdash . .

USER freshdash

# Collect static files for WhiteNoise
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Copy and grant entrypoint execution
ENTRYPOINT ["/bin/sh", "entrypoint.sh"]

