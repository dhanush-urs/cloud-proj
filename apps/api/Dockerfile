FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    bash \
    libreoffice-impress \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd -r repobrain && useradd -r -g repobrain repobrain

COPY requirements.txt .
COPY requirements-dev.txt .

RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

# Ensure the data directories exist and are owned by the non-root user
RUN mkdir -p /app/data/repos /app/data/tmp \
    && chown -R repobrain:repobrain /app

USER repobrain

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]