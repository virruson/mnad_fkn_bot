# Dockerfile
FROM python:3.11-slim-bookworm

WORKDIR /app

# Установка системных зависимостей 
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/
COPY scripts/ ./scripts/
COPY .env .

RUN mkdir -p /app/data /app/logs

CMD ["python", "-m", "bot.main"]