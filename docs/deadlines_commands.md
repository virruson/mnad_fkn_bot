# Дедлайны: команды

## Первый запуск

Мак:
```bash
cd ~/Claude/hse_bot
rm .git/index.lock                  # старый лок git (разово)
git add .gitignore bot scripts tests docs README.md requirements.txt
git commit -m "Дедлайны + переключатели уведомлений"
git push
```

Сервер:
```bash
cd ~/mnad_bot
./scripts/deploy.sh                 # pull + пересборка + миграция + импорт дедлайнов
docker-compose restart bot          # перезапуск после миграции
docker-compose logs --tail=20 bot | grep NOTIFY   # планировщик стартовал
```

## Обновить дедлайны

```bash
# мак: правим scripts/deadlines.json
git commit -am "Дедлайны" && git push
# сервер:
./scripts/deploy.sh                 # импорт запустится сам, если json изменился
```

## Формат scripts/deadlines.json

```json
{
  "modules":   [{"name": "5 модуль", "start": "05.09.2026", "end": "26.10.2026"}],
  "subjects":  [{"name": "Продвинутое машинное обучение", "short_name": "Продвинутое МО", "formula": "0.3·ДЗ + 0.2·Квизы + 0.5·КР"}],
  "deadlines": [{"subject": "Продвинутое машинное обучение", "type": "ДЗ", "title": "№1", "date": "03.10.2026", "time": "18:00"}]
}
```
- `subject` / `name` — точное название из расписания, иначе WARNING и пропуск
- `type` — ДЗ / Квиз / КВИЗ/КР / КР / Экзамен / Этап (у экзамена `title` можно оставить пустым)
- предмета нет в расписании (ВКР) — в `subjects` добавить `"create": true`
- `short_name` с эмодзи (`📜 ВКР`) — так предмет помечается на кнопке и в рассылке
- `time` можно не писать → 23:59
- импорт только добавляет и обновляет, ничего не удаляет

## Вручную на сервере

```bash
docker-compose exec bot python -m scripts.import_deadlines --dry-run   # что загрузится
docker-compose exec bot python -m scripts.import_deadlines             # загрузить
docker-compose exec postgres psql -U mnad_bot -d mnad_schedule -c "select version_num from alembic_version"   # версия БД
docker-compose run --rm postgres-migrate alembic downgrade -1          # откат миграции
```

## Тест рассылки на дату

Уходит реальное сообщение всем, у кого включены «Дедлайны».
```bash
docker-compose exec -T bot python - <<'PY'
import asyncio, os, datetime
from telegram import Bot
from bot.services.scheduler import send_deadline_digest
async def main():
    async with Bot(os.environ["BOT_TOKEN"]) as b:
        print(await send_deadline_digest(b, datetime.date(2026, 10, 1)))
asyncio.run(main())
PY
```
