# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (separate layer for caching)
COPY server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application code
COPY server/ .

# Non-root user
RUN useradd -m -u 1001 appuser && chown -R appuser /app
USER appuser

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "--access-logfile", "-", "app:app"]
