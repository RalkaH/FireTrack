# routers/backups.py (v1.0)
"""
Резервные копии базы в админке (только администратор).

Копию можно создать и скачать. В копии есть хеши паролей, поэтому каждое
скачивание пишется в журнал действий. Восстановление из копии намеренно
делается вручную при остановленном сервере (см. README).
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

import audit
import backup
from auth import ROLE_ADMIN, get_current_active_user, require_role
from db import get_db
from models import User

_admin_only = require_role([ROLE_ADMIN])

router = APIRouter(
    prefix="/backups",
    tags=["Backups"],
    dependencies=[Depends(get_current_active_user), Depends(_admin_only)],
)


@router.get("/")
def list_backups():
    """
    Список резервных копий, новые сверху.

    Returns:
        list: Имя, тип (auto, manual, migration), размер и время создания.
    """
    return backup.list_backups()


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_backup(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin_only),
):
    """
    Создать резервную копию сейчас.

    Args:
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Администратор.

    Returns:
        dict: Имя созданного файла.

    Raises:
        HTTPException: Если база хранится не в файле SQLite (400).
    """
    path = backup.create_backup("manual", db.get_bind())
    if path is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Резервные копии доступны только для базы SQLite в файле")
    audit.log(db, request, current_user, audit.ACTION_BACKUP, f"Создана копия базы {path.name}",
              entity_type="backup", commit=True)
    return {"name": path.name}


@router.get("/{name}")
def download_backup(
    name: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin_only),
):
    """
    Скачать резервную копию.

    Args:
        name (str): Имя файла из списка копий.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Администратор.

    Returns:
        FileResponse: Файл копии.

    Raises:
        HTTPException: Если такого файла нет или имя недопустимо (404).
    """
    path = backup.resolve_backup(name)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Копия не найдена")
    audit.log(db, request, current_user, audit.ACTION_BACKUP, f"Скачана копия базы {path.name}",
              entity_type="backup", commit=True)
    return FileResponse(path, media_type="application/octet-stream", filename=path.name)
