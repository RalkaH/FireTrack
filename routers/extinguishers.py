# routers/extinguishers.py (v1.3)
"""
Модуль для управления огнетушителями (CRUD операции).
Включает фильтрацию, поиск по инвентарному номеру, создание, обновление,
удаление оборудования и отметку о перезарядке.

В каждом ответе есть вычисляемые сроки: вид ОТВ, дата следующей
перезарядки и конец срока службы (см. модуль ``deadlines``).
Все изменения пишутся в журнал действий.
"""
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

import audit
from app_settings import get_settings
from auth import EDITOR_ROLES, ROLE_ADMIN, get_current_active_user, require_role
from db import get_db
from deadlines import compute_deadlines
from models import User, FireExtinguisher, Location, Status, Inspection
from schemas import (
    FireExtinguisherCreate,
    FireExtinguisherRead,
    FireExtinguisherUpdate,
    RechargeMark,
)
from status_logic import STATUS_DECOMMISSIONED, recalculate_statuses

router = APIRouter(
    prefix="/extinguishers",
    tags=["Fire Extinguishers"],
    dependencies=[Depends(get_current_active_user)],
)

AUDIT_FIELDS = (
    "inventory_number", "type", "capacity", "manufacturer", "manufacture_date",
    "commissioning_date", "location_id", "status_id", "last_recharge_date",
    "recharge_interval_months", "service_life_years",
)
# Поля, от которых зависят сроки перезарядки (и значит статус)
DEADLINE_FIELDS = {"type", "manufacture_date", "commissioning_date", "last_recharge_date",
                   "recharge_interval_months", "service_life_years"}


def serialize(fe: FireExtinguisher, settings: Dict[str, Any],
              today: Optional[date] = None) -> Dict[str, Any]:
    """
    Огнетушитель вместе с вычисленными сроками.

    Args:
        fe (FireExtinguisher): Огнетушитель.
        settings (Dict[str, Any]): Настройки приложения.
        today (Optional[date]): Текущая дата.

    Returns:
        Dict[str, Any]: Данные по схеме ``FireExtinguisherRead``.
    """
    data = FireExtinguisherRead.model_validate(fe).model_dump()
    d = compute_deadlines(fe, settings, today)
    data.update({
        "agent_label": d["agent_label"],
        "effective_recharge_interval_months": d["recharge_interval_months"],
        "next_recharge_date": d["next_recharge_date"],
        "recharge_days_left": d["recharge_days_left"],
        "recharge_state": d["recharge_state"],
        "effective_service_life_years": d["service_life_years"],
        "service_end_date": d["service_end_date"],
        "service_state": d["service_state"],
    })
    return data


def _get_or_404(db: Session, extinguisher_id: int) -> FireExtinguisher:
    """Возвращает огнетушитель или 404."""
    extinguisher = db.get(FireExtinguisher, extinguisher_id)
    if extinguisher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Огнетушитель не найден")
    return extinguisher


def _check_relations(db: Session, location_id: Optional[int], status_id: Optional[int]) -> None:
    """Проверяет существование места и статуса."""
    if location_id is not None and db.get(Location, location_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Место расположения не найдено")
    if status_id is not None and db.get(Status, status_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Статус не найден")


@router.get("/", response_model=List[FireExtinguisherRead])
def list_extinguishers(
    location_id: Optional[int] = Query(None, description="Фильтр по ID места"),
    status_id: Optional[int] = Query(None, description="Фильтр по ID статуса"),
    db: Session = Depends(get_db),
):
    """
    Получить список всех огнетушителей с возможностью фильтрации.

    Args:
        location_id (Optional[int]): ID местоположения для фильтрации.
        status_id (Optional[int]): ID статуса для фильтрации.
        db (Session): Сессия базы данных.

    Returns:
        List[dict]: Отфильтрованный список оборудования со сроками.
    """
    query = db.query(FireExtinguisher)

    if location_id is not None:
        query = query.filter(FireExtinguisher.location_id == location_id)

    if status_id is not None:
        query = query.filter(FireExtinguisher.status_id == status_id)

    settings = get_settings(db)
    today = date.today()
    return [serialize(fe, settings, today)
            for fe in query.order_by(FireExtinguisher.inventory_number).all()]


@router.get("/search/inventory", response_model=List[FireExtinguisherRead])
def search_by_inventory(
    query: str = Query(..., min_length=1,
                       description="Поисковый запрос по инвентарному номеру"),
    db: Session = Depends(get_db),
):
    """
    Поиск огнетушителей по инвентарному номеру (частичное совпадение).

    Args:
        query (str): Подстрока инвентарного номера для поиска.
        db (Session): Сессия базы данных.

    Returns:
        List[dict]: Список найденного оборудования.
    """
    settings = get_settings(db)
    results = (
        db.query(FireExtinguisher)
        .filter(FireExtinguisher.inventory_number.contains(query))
        .order_by(FireExtinguisher.inventory_number)
        .all()
    )
    return [serialize(fe, settings) for fe in results]


@router.get("/{extinguisher_id}", response_model=FireExtinguisherRead)
def get_extinguisher(
    extinguisher_id: int,
    db: Session = Depends(get_db),
):
    """
    Получить детальную информацию об огнетушителе по его ID.

    Args:
        extinguisher_id (int): Уникальный идентификатор огнетушителя.
        db (Session): Сессия базы данных.

    Returns:
        dict: Огнетушитель со сроками.

    Raises:
        HTTPException: Если огнетушитель с указанным ID не найден (404).
    """
    return serialize(_get_or_404(db, extinguisher_id), get_settings(db))


@router.post("/", response_model=FireExtinguisherRead, status_code=status.HTTP_201_CREATED)
def create_extinguisher(
    data: FireExtinguisherCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(EDITOR_ROLES))
):
    """
    Добавить новый огнетушитель в систему. Доступно только администраторам и инженерам.

    Args:
        data (FireExtinguisherCreate): Данные для создания.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Авторизованный пользователь с соответствующей ролью.

    Returns:
        dict: Созданный огнетушитель со сроками.

    Raises:
        HTTPException: В случае дубликата инвентарного номера или отсутствия
            связанных объектов (локации/статуса).
    """
    existing = (
        db.query(FireExtinguisher)
        .filter(FireExtinguisher.inventory_number == data.inventory_number)
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Огнетушитель с инвентарным номером '{data.inventory_number}' уже существует",
        )

    # Даты из будущего отсекаются валидатором схемы
    _check_relations(db, data.location_id, data.status_id)

    now = datetime.now(timezone.utc)
    extinguisher = FireExtinguisher(**data.model_dump(), created_at=now, updated_at=now)
    db.add(extinguisher)
    db.flush()
    audit.log(db, request, current_user, audit.ACTION_CREATE,
              f"Добавлен огнетушитель {extinguisher.inventory_number}",
              entity_type="extinguisher", entity_id=extinguisher.id,
              changes=audit.diff({}, audit.snapshot(extinguisher, AUDIT_FIELDS)))
    db.commit()
    db.refresh(extinguisher)

    return serialize(extinguisher, get_settings(db))


@router.put("/{extinguisher_id}", response_model=FireExtinguisherRead)
def update_extinguisher(
    extinguisher_id: int,
    data: FireExtinguisherUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(EDITOR_ROLES))
):
    """
    Обновить данные существующего огнетушителя. Доступно только администраторам и инженерам.

    Если изменились поля, от которых зависят сроки перезарядки, а статус
    вручную не меняли, статус пересчитывается.

    Args:
        extinguisher_id (int): Идентификатор обновляемого огнетушителя.
        data (FireExtinguisherUpdate): Новые данные.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Авторизованный пользователь с соответствующей ролью.

    Returns:
        dict: Обновленный огнетушитель со сроками.

    Raises:
        HTTPException: Если объект не найден, дублируется номер или указаны
            неверные связанные ключи.
    """
    extinguisher = _get_or_404(db, extinguisher_id)

    if data.inventory_number is not None:
        existing = (
            db.query(FireExtinguisher)
            .filter(
                FireExtinguisher.inventory_number == data.inventory_number,
                FireExtinguisher.id != extinguisher_id,
            )
            .first()
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Огнетушитель с инвентарным номером '{data.inventory_number}' уже существует",
            )

    _check_relations(db, data.location_id, data.status_id)

    update_data = data.model_dump(exclude_unset=True)

    # Обязательные поля нельзя очистить
    for required_field in ("inventory_number", "type", "capacity", "location_id", "status_id"):
        if required_field in update_data and update_data[required_field] is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Поле '{required_field}' не может быть пустым",
            )

    before = audit.snapshot(extinguisher, AUDIT_FIELDS)
    for field, value in update_data.items():
        setattr(extinguisher, field, value)
    changes = audit.diff(before, audit.snapshot(extinguisher, AUDIT_FIELDS))

    if changes:
        extinguisher.updated_at = datetime.now(timezone.utc)
        audit.log(db, request, current_user, audit.ACTION_UPDATE,
                  f"Изменен огнетушитель {extinguisher.inventory_number}",
                  entity_type="extinguisher", entity_id=extinguisher.id, changes=changes)
    db.commit()

    if DEADLINE_FIELDS & set(changes) and "status_id" not in changes:
        recalculate_statuses(db, extinguisher_ids=[extinguisher.id])
    db.refresh(extinguisher)

    return serialize(extinguisher, get_settings(db))


@router.post("/{extinguisher_id}/recharge", response_model=FireExtinguisherRead)
def mark_recharged(
    extinguisher_id: int,
    data: RechargeMark,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(EDITOR_ROLES)),
):
    """
    Отметить перезарядку огнетушителя.

    Сохраняет дату перезарядки (и, если указан, новый интервал по паспорту),
    пишет событие в журнал действий и пересчитывает статус
    (кроме списанных огнетушителей).

    Args:
        extinguisher_id (int): ID огнетушителя.
        data (RechargeMark): Дата перезарядки, интервал и комментарий.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Инженер или администратор.

    Returns:
        dict: Огнетушитель с новыми сроками.
    """
    extinguisher = _get_or_404(db, extinguisher_id)
    before = audit.snapshot(extinguisher, AUDIT_FIELDS)
    extinguisher.last_recharge_date = data.recharge_date
    if data.recharge_interval_months is not None:
        extinguisher.recharge_interval_months = data.recharge_interval_months
    extinguisher.updated_at = datetime.now(timezone.utc)

    summary = f"Отмечена перезарядка огнетушителя {extinguisher.inventory_number} от {data.recharge_date:%d.%m.%Y}"
    if data.comment:
        summary += f" ({data.comment.strip()})"
    audit.log(db, request, current_user, audit.ACTION_UPDATE, summary,
              entity_type="extinguisher", entity_id=extinguisher.id,
              changes=audit.diff(before, audit.snapshot(extinguisher, AUDIT_FIELDS)))
    db.commit()

    recalculate_statuses(db, extinguisher_ids=[extinguisher.id], keep_manual=[STATUS_DECOMMISSIONED])
    db.refresh(extinguisher)
    return serialize(extinguisher, get_settings(db))


@router.delete("/{extinguisher_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_extinguisher(
    extinguisher_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ROLE_ADMIN]))
):
    """
    Полностью удалить огнетушитель и всю историю его проверок (каскадное удаление).
    Доступно ИСКЛЮЧИТЕЛЬНО администраторам.

    В журнал действий сохраняется карточка огнетушителя и число удаленных
    проверок, чтобы удаление можно было восстановить по журналу.

    Args:
        extinguisher_id (int): Идентификатор удаляемого оборудования.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Текущий администратор.

    Returns:
        None

    Raises:
        HTTPException: Если огнетушитель не найден.
    """
    extinguisher = _get_or_404(db, extinguisher_id)
    card = audit.snapshot(extinguisher, AUDIT_FIELDS)

    removed = db.query(Inspection).filter(
        Inspection.fire_extinguisher_id == extinguisher_id
    ).delete()

    audit.log(db, request, current_user, audit.ACTION_DELETE,
              f"Удален огнетушитель {extinguisher.inventory_number} и {removed} проверок",
              entity_type="extinguisher", entity_id=extinguisher.id,
              changes={k: {"old": v, "new": None} for k, v in card.items()})
    db.delete(extinguisher)
    db.commit()

    return None
