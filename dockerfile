# Dockerfile
FROM python:3.9-slim

# Установка рабочей директории
WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода бота
COPY bot/ ./bot/
COPY .env .

# Создание директории для данных
RUN mkdir -p /app/data

# Запуск бота
CMD ["python", "-m", "bot.main"]