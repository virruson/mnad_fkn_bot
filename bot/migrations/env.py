# migrations/env.py
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Это твои SQLAlchemy модели
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from bot.utils.database import Base
from bot.models import *  # Импортируем все модели

# this is the Alembic Config object
config = context.config

# Интерпретируем файл конфигурации логирования
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Устанавливаем target_metadata из моделей
target_metadata = Base.metadata

# Получаем URL базы данных из переменной окружения
def get_url():
    return os.getenv("DATABASE_URL", "postgresql://mnad_bot:mnad_password@localhost:5432/mnad_schedule")

def run_migrations_offline() -> None:
    """Запуск миграций в 'offline' режиме."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Запуск миграций в 'online' режиме."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()