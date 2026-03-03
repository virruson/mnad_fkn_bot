#!/bin/bash
# run_docker.sh

echo "Запуск бота в Docker-контейнере..."

# Сборка образа
docker-compose build

# Запуск контейнера
docker-compose up -d

# Просмотр логов
docker-compose logs -f