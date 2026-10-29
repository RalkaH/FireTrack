# routers/statuses.py (v1.2)
"""
Модуль для управления техническими статусами оборудования.
Включает инициализацию дефолтных системных статусов и пересчет актуальности.
Сама логика расчета статусов находится в модуле status_logic.
"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import EDITOR_ROLES, ROLE_ADMIN, get_current_active_user, require_role
from db import get_db
from models import Status, User
from schemas import StatusCreate, StatusRead
from status_logic import ensure_default_statuses, recalculate_statuses


router = APIRouter(
    prefix="/statuses",
    tags=["Statuses"],
    dependencies=[Depends(get_current_active_user)],
)


@router.get("/", response_model=List[StatusRead])
def list_statuses(db: Session = Depends(get_db)):
    """
    Получить справочник всех возможных статусов оборудования.

    Args:
        db (Session): Сессия БД.

    Returns:
        List[Status]: Список статусов.
    """
    return db.query(Status).order_by(Status.id).all()


@router.post(
    "/",
    response_model=StatusRead,
    status_code=status.HTTP_201_CREATED,
)
def create_status(
    data: StatusCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ROLE_ADMIN])),
):
    """
    Зарегистрировать новый кастомный статус. Доступно только администраторам.

    Args:
        data (StatusCreate): Наименование и описание статуса.
        db (Session): Сессия БД.
        current_user (User): Текущий администратор.

    Returns:
        Status: Созданный объект.

    Raises:
        HTTPException: Если статус с таким именем уже существует.
    """
    name = data.name.strip()
    existing = db.query(Status).filter(Status.name == name).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Статус с таким названием уже существует",
        )

    status_obj = Status(
        name=name,
        description=data.description,
        created_at=datetime.now(timezone.utc),
    )

    db.add(status_obj)
    db.commit()
    db.refresh(status_obj)

    return status_obj


@router.post("/init-defaults", status_code=status.HTTP_201_CREATED)
def init_default_statuses(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ROLE_ADMIN])),
):
    """
    Инициализировать стандартные статусы системы.
    Создает записи только если они отсутствуют в базе.

    Args:
        db (Session): Сессия БД.
        current_user (User): Текущий администратор.

    Returns:
        dict: Статистика инициализации.
    """
    created = ensure_default_statuses(db)
    return {
        "detail": "Инициализация завершена",
        "created": created,
    }


@router.post("/recalculate")
def recalculate_statuses_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(EDITOR_ROLES)),
):
    """
    Массовый пересчет статусов всего парка огнетушителей на основе последних проверок.

    Статусы «Списан» и «На техническом обслуживании» не меняются.
    Остальные огнетушители получают «Актуально», «Просрочено» или
    «Требует обслуживания» (если при последней проверке найдены дефекты).

    Args:
        db (Session): Сессия БД.
        current_user (User): Пользователь с правами инженера или администратора.

    Returns:
        dict: Сообщение и количество измененных статусов.
    """
    changed = recalculate_statuses(db)
    return {"detail": "Статусы пересчитаны", "changed": changed}
