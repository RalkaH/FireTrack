# routers/settings.py (v1.0)
"""
Настройки приложения: шапка отчетов и сроки перезарядки по умолчанию.

Читать настройки может любой вошедший пользователь (они нужны формам
и отчетам), менять только администратор. Изменение пересчитывает
статусы, потому что от интервалов перезарядки зависит «Требует
обслуживания».
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

import audit
from app_settings import DEFAULTS, LABELS, LIMITS, get_settings, update_settings
from auth import ROLE_ADMIN, get_current_active_user, require_role
from db import get_db
from models import User
from status_logic import recalculate_statuses

router = APIRouter(
    prefix="/settings",
    tags=["Settings"],
    dependencies=[Depends(get_current_active_user)],
)


@router.get("/")
def read_settings(db: Session = Depends(get_db)):
    """
    Текущие настройки, значения по умолчанию, подписи и допустимые диапазоны.

    Returns:
        dict: ``values``, ``defaults``, ``labels``, ``limits``.
    """
    return {
        "values": get_settings(db),
        "defaults": DEFAULTS,
        "labels": LABELS,
        "limits": {k: {"min": v[0], "max": v[1]} for k, v in LIMITS.items()},
    }


@router.put("/")
def save_settings(
    values: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ROLE_ADMIN])),
):
    """
    Сохранить настройки (можно передать только часть ключей).

    Args:
        values (Dict[str, Any]): Новые значения.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Администратор.

    Returns:
        dict: Настройки после сохранения и число огнетушителей,
        у которых изменился статус.

    Raises:
        HTTPException: Неизвестный ключ или неверное значение (422).
    """
    try:
        changes = update_settings(db, values)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if changes:
        audit.log(db, request, current_user, audit.ACTION_UPDATE,
                  "Изменены настройки: " + ", ".join(LABELS.get(k, k) for k in changes),
                  entity_type="settings", changes=changes)
    db.commit()
    changed_statuses = recalculate_statuses(db) if changes else 0
    return {"values": get_settings(db), "changed_statuses": changed_statuses}
