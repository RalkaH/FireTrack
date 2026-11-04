# migrations/env.py (v1.0)
"""
Окружение Alembic для FireTrack.

URL базы и метаданные берутся из приложения (``db.py`` и ``models.py``),
поэтому миграции всегда работают с той же базой, что и сервер.
``render_as_batch=True`` обязателен: SQLite не умеет большинство ALTER TABLE,
и Alembic в batch-режиме пересоздает таблицу с сохранением данных.
"""
from logging.config import fileConfig

from alembic import context

from db import Base, DATABASE_URL, engine
import models  # noqa: F401  (регистрирует таблицы в Base.metadata)

config = context.config

# Логирование настраиваем только при запуске из командной строки alembic,
# чтобы не перебивать настройки логов работающего сервера.
if config.config_file_name is not None and "connection" not in config.attributes:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _configure_and_run(connection) -> None:
    """Настраивает контекст миграций на соединении и выполняет их."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """Генерирует SQL без подключения к базе (``alembic upgrade head --sql``)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Выполняет миграции на живой базе."""
    connection = config.attributes.get("connection")
    if connection is not None:
        # Вызов из приложения (migrate.py): соединение уже открыто
        _configure_and_run(connection)
        return
    with engine.connect() as conn:
        _configure_and_run(conn)
        conn.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
