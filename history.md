git status
git add .gitignore README.md # git add .

git commit -m "Initial commit: add .gitignore and README"

# отправить на GitHub
git push origin main -m "asdadqwd"

# откатить изменения
git checkout 70f1b3521f6f76e99751a506e6e0cc096ee27967 -- dockerfile


# создадим окружение
python3 -m venv venv

# активация
source venv/bin/activate

# проверка
which python  # должно показать ./venv/bin/python
python tests/test_connection.py

# пополняем requirements.txt нужными пакетами и устанавливаем
pip install -r requirements.txt
pip list

# зафиксировать версии
pip freeze > requirements.txt  

# Запуск всех сервисов
docker-compose up -d

# Запуск только БД и бота (без pgAdmin)
docker-compose --profile dev up -d postgres bot

# Запуск с pgAdmin (для разработки)
docker-compose --profile dev up -d

# Просмотр логов БД
docker-compose logs -f postgres

# Подключение к PostgreSQL внутри контейнера
docker exec -it mnad_fkn_postgres psql -U mnad_bot -d mnad_schedule

# Бэкап и восстановление базы данных
docker exec mnad_fkn_postgres pg_dump -U mnad_bot mnad_schedule > backup.sql
cat backup.sql | docker exec -i mnad_fkn_postgres psql -U mnad_bot -d mnad_schedule


# Подключиться к БД и посмотреть таблицы
docker exec -it mnad_fkn_postgres psql -U mnad_bot -d mnad_schedule

# В psql:
\dt
SELECT * FROM teachers;
SELECT * FROM lesson_types;
SELECT * FROM streams;

# Выйти из psql
\q