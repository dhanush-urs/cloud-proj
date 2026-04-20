# --- Build Stage ---
FROM python:3.13-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Production Stage ---
FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    git \
    curl \
    libreoffice-impress \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd -r repobrain && useradd -r -g repobrain repobrain

COPY --from=builder /install /usr/local
COPY apps/api .

# Initialize data directories and set permissions
RUN mkdir -p /app/data/repos /app/data/tmp \
    && chown -R repobrain:repobrain /app

# Set environment variables
ENV PYTHONPATH=/app
ENV APP_ENV=production
ENV PYTHONUNBUFFERED=1

USER repobrain

EXPOSE 8000

# FIX 3: Retry Alembic until DB is ready, then start the server
CMD ["sh", "-c", "until alembic upgrade head; do echo 'Waiting for DB to be ready... retrying in 3s'; sleep 3; done && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
