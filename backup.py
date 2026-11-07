# backup.py (v1.0)
"""
Резервные копии базы данных SQLite.

Копии лежат в папке ``backups`` (та же, что и для копий перед миграциями):

* ``<база>_auto_<время>.db`` — автоматические, не чаще раза в сутки,
  хранятся последние N штук (настройка ``backup_keep_count``);
* ``<база>_manual_<время>.db`` — созданные вручную из админки;
* ``<база>_<время>_before_<ревизия>.db`` — перед миграциями.

Вручную созданные копии и копии перед миграциями автоматически не удаляются.
Копирование идет через штатный механизм резервирования SQLite, поэтому копия
целостна, даже если в этот момент сервер пишет в базу.
"""
import logging
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.engine import Engine

import migrate
from db import engine as default_engine

logger = logging.getLogger("firetrack.backup")

AUTO_INTERVAL = timedelta(hours=24)
_SAFE_NAME = re.compile(r"^[\w.\-]+\.db$")


def backup_dir() -> Path:
    """Папка резервных копий."""
    return Path(migrate.BACKUP_DIR)


def create_backup(kind: str = "manual", engine: Engine = default_engine) -> Optional[Path]:
    """
    Создает копию базы.

    Args:
        kind (str): ``auto`` или ``manual``.
        engine (Engine): Движок базы.

    Returns:
        Optional[Path]: Путь к копии или None, если база не в файле SQLite.
    """
    source = migrate.sqlite_file(engine)
    if source is None or not source.exists():
        return None
    folder = backup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = folder / f"{source.stem}_{kind}_{stamp}{source.suffix}"

    src = sqlite3.connect(source)
    dst = sqlite3.connect(target)
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()
    return target


def list_backups() -> List[Dict[str, object]]:
    """
    Список копий, новые сверху.

    Returns:
        List[Dict[str, object]]: Имя, тип, размер в байтах и время создания (UTC).
    """
    folder = backup_dir()
    if not folder.exists():
        return []
    result = []
    for path in folder.glob("*.db"):
        stat = path.stat()
        if "_auto_" in path.name:
            kind = "auto"
        elif "_before_" in path.name:
            kind = "migration"
        else:
            kind = "manual"
        result.append({
            "name": path.name,
            "kind": kind,
            "size": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    result.sort(key=lambda item: item["created_at"], reverse=True)
    return result


def resolve_backup(name: str) -> Optional[Path]:
    """
    Находит файл копии по имени, не выпуская запрос за пределы папки копий.

    Args:
        name (str): Имя файла.

    Returns:
        Optional[Path]: Путь к файлу или None, если имя недопустимо или файла нет.
    """
    if not _SAFE_NAME.match(name) or ".." in name:
        return None
    path = backup_dir() / name
    return path if path.is_file() else None


def prune_auto_backups(keep: int) -> int:
    """
    Удаляет старые автоматические копии.

    Args:
        keep (int): Сколько последних копий оставить.

    Returns:
        int: Сколько файлов удалено.
    """
    folder = backup_dir()
    if not folder.exists():
        return 0
    files = sorted(folder.glob("*_auto_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = 0
    for path in files[keep:]:
        path.unlink(missing_ok=True)
        removed += 1
    return removed


def run_scheduled_backup(keep: int, engine: Engine = default_engine) -> Optional[Path]:
    """
    Делает автоматическую копию, если с прошлой прошло не меньше суток.

    Args:
        keep (int): Сколько автоматических копий хранить.
        engine (Engine): Движок базы.

    Returns:
        Optional[Path]: Путь к новой копии или None, если копия не нужна.
    """
    folder = backup_dir()
    if folder.exists():
        files = list(folder.glob("*_auto_*.db"))
        if files:
            newest = max(p.stat().st_mtime for p in files)
            if datetime.now() - datetime.fromtimestamp(newest) < AUTO_INTERVAL:
                return None
    path = create_backup("auto", engine)
    if path is not None:
        prune_auto_backups(keep)
        logger.info("Автокопия базы: %s", path)
    return path
