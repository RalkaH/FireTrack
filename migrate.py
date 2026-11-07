# migrate.py (v1.1)
"""
Обновление схемы базы данных через Alembic.

Приложение вызывает :func:`upgrade_database` при каждом запуске, поэтому
вручную обычно ничего делать не нужно. Порядок работы:

1. Если в базе уже есть таблицы FireTrack, но нет таблицы ``alembic_version``
   (база создана до V4 через ``create_all``), база помечается ревизией
   ``0001_baseline`` без изменений.
2. Если есть невыполненные миграции и база хранится в файле SQLite,
   перед изменениями делается резервная копия в папку ``backups``.
3. Выполняется ``upgrade head``.

Запуск вручную из корня проекта: ``python migrate.py``.
"""
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from db import engine as default_engine

logger = logging.getLogger("firetrack.migrate")

BASE_DIR = Path(__file__).resolve().parent
BASELINE_REVISION = "0001_baseline"
LEGACY_TABLES = {"Locations", "Statuses", "FireExtinguishers",
                 "Employees", "Inspections", "Users"}
BACKUP_DIR = BASE_DIR / "backups"


def _alembic_config() -> Config:
    """Создает конфигурацию Alembic, не зависящую от текущей папки."""
    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BASE_DIR / "migrations"))
    return cfg


def sqlite_file(engine: Engine) -> Optional[Path]:
    """Возвращает путь к файлу SQLite или None для других баз и баз в памяти."""
    url = engine.url
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return None
    path = Path(url.database)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def backup_database(engine: Engine, label: str) -> Optional[Path]:
    """
    Делает копию файла SQLite перед изменением схемы.

    Args:
        engine (Engine): Движок базы.
        label (str): Метка для имени файла (например, целевая ревизия).

    Returns:
        Optional[Path]: Путь к копии или None, если копировать нечего.
    """
    source = sqlite_file(engine)
    if source is None or not source.exists():
        return None
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = BACKUP_DIR / f"{source.stem}_{stamp}_before_{label}{source.suffix}"
    shutil.copy2(source, target)
    return target


def upgrade_database(engine: Engine = default_engine) -> Optional[str]:
    """
    Доводит схему базы до последней ревизии.

    Args:
        engine (Engine): Движок базы (по умолчанию из ``db.py``).

    Returns:
        Optional[str]: Ревизия базы после обновления.
    """
    cfg = _alembic_config()
    head = ScriptDirectory.from_config(cfg).get_current_head()

    with engine.connect() as conn:
        tables = set(inspect(conn).get_table_names())
        current = MigrationContext.configure(conn).get_current_revision()

    if current is None and tables & LEGACY_TABLES:
        logger.info("База создана до миграций, помечаю ревизией %s", BASELINE_REVISION)
        current = BASELINE_REVISION
        stamp_needed = True
    else:
        stamp_needed = False

    if current != head and current is not None:
        backup = backup_database(engine, head)
        if backup is not None:
            logger.info("Резервная копия базы перед миграцией: %s", backup)

    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        if stamp_needed:
            command.stamp(cfg, BASELINE_REVISION)
        command.upgrade(cfg, "head")

    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print("Версия схемы:", upgrade_database())
