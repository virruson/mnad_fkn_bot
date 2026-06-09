#!/bin/bash
# scripts/deploy.sh
#
# Простое обновление бота на сервере "по команде":
#   1) подтягивает последний код из git
#   2) пересобирает образ бота
#   3) прогоняет миграции БД
#   4) перезапускает контейнеры
#
# Установка (один раз на сервере):
#   chmod +x scripts/deploy.sh
#   ln -s ~/mnad_bot/scripts/deploy.sh ~/deploy.sh   # по желанию, для удобства
#
# Запуск (когда нужно обновить бота):
#   ssh username@server_ip "cd ~/mnad_bot && ./scripts/deploy.sh"
# или зайдя на сервер по SSH и выполнив:
#   ./scripts/deploy.sh

set -euo pipefail
cd "$(dirname "$0")/.."   # переходим в корень проекта (на уровень выше scripts/)

echo "=== [1/4] Проверка статуса git ==="
if [ -n "$(git status --porcelain)" ]; then
    echo "⚠️  В рабочей копии есть незакоммиченные изменения:"
    git status --short
    read -p "Продолжить и выполнить 'git pull' поверх них? [y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]] || { echo "Отменено."; exit 1; }
fi

echo ""
echo "=== [2/4] Обновление кода (git pull) ==="
git pull --ff-only

echo ""
echo "=== [3/4] Пересборка и запуск контейнеров ==="
docker-compose build bot
docker-compose up -d --remove-orphans postgres bot

echo ""
echo "=== [4/4] Применение миграций БД ==="
docker-compose run --rm postgres-migrate

echo ""
echo "=== Готово. Текущий статус контейнеров: ==="
docker-compose ps

echo ""
echo "Последние строки логов бота:"
docker-compose logs --tail=20 bot
