# routers/service_records.py (v1.0)
"""
История технического обслуживания огнетушителей: испытания, перезарядка, ремонт.

Записи соответствуют графам формы А.2 приложения А ГОСТ Р 59641-2021.
Добавлять записи могут инженер и администратор, исправлять и удалять
только администратор. Даты последней перезарядки и испытания в карточке
огнетушителя пересчитываются по истории, затем пересчитывается статус.
"""
from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

import audit
from app_settings import get_settings
from auth import EDITOR_ROLES, ROLE_ADMIN, get_current_active_user, require_role
from db import get_db
from models import FireExtinguisher, ServiceRecord, User
from schemas import ServiceRecordCreate, ServiceRecordRead, ServiceRecordUpdate
from service_logic import default_next_dates, sync_extinguisher_dates
from status_logic import STATUS_DECOMMISSIONED, recalculate_statuses

router = APIRouter(
    prefix="/service-records",
    tags=["Service records"],
    dependencies=[Depends(get_current_active_user)],
)

AUDIT_FIELDS = (
    "fire_extinguisher_id", "service_date", "tested", "recharged", "repaired", "organization",
    "test_result", "next_test_date", "agent_brand", "post_recharge_result",
    "next_recharge_date", "responsible", "comments",
)
EDITABLE_FIELDS = tuple(f for f in AUDIT_FIELDS if f != "fire_extinguisher_id")


def _work_text(record: ServiceRecord) -> str:
    """Виды выполненных работ одной строкой."""
    works = [name for flag, name in ((record.tested, "испытание"), (record.recharged, "перезарядка"),
                                     (record.repaired, "ремонт")) if flag]
    return ", ".join(works)


def _get_or_404(db: Session, record_id: int) -> ServiceRecord:
    """Возвращает запись или 404."""
    record = db.get(ServiceRecord, record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись о ТО не найдена")
    return record


def _apply(record: ServiceRecord, data, fe: FireExtinguisher, settings: dict) -> None:
    """Переносит поля формы в запись и подставляет следующие сроки по умолчанию."""
    for field in EDITABLE_FIELDS:
        value = getattr(data, field)
        setattr(record, field, value.strip() or None if isinstance(value, str) else value)
    defaults = default_next_dates(fe, settings, record.service_date, record.tested, record.recharged)
    record.next_test_date = (record.next_test_date or defaults["next_test_date"]) if record.tested else None
    record.next_recharge_date = (record.next_recharge_date or defaults["next_recharge_date"]) if record.recharged else None


@router.get("/", response_model=List[ServiceRecordRead])
def list_service_records(
    extinguisher_id: Optional[int] = Query(None, description="Фильтр по огнетушителю"),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """
    История ТО, новые записи сверху.

    Args:
        extinguisher_id (Optional[int]): ID огнетушителя.
        date_from (Optional[date]): С даты.
        date_to (Optional[date]): По дату.
        db (Session): Сессия базы данных.

    Returns:
        List[ServiceRecord]: Записи о ТО.
    """
    query = db.query(ServiceRecord)
    if extinguisher_id is not None:
        query = query.filter(ServiceRecord.fire_extinguisher_id == extinguisher_id)
    if date_from is not None:
        query = query.filter(ServiceRecord.service_date >= date_from)
    if date_to is not None:
        query = query.filter(ServiceRecord.service_date <= date_to)
    return query.order_by(ServiceRecord.service_date.desc(), ServiceRecord.id.desc()).all()


@router.post("/", response_model=ServiceRecordRead, status_code=status.HTTP_201_CREATED)
def create_service_record(
    data: ServiceRecordCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(EDITOR_ROLES)),
):
    """
    Добавить запись о ТО. Статус огнетушителя пересчитывается (кроме списанного).

    Args:
        data (ServiceRecordCreate): Данные записи.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Инженер или администратор.

    Returns:
        ServiceRecord: Созданная запись.

    Raises:
        HTTPException: Если огнетушитель не найден (400).
    """
    fe = db.get(FireExtinguisher, data.fire_extinguisher_id)
    if fe is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Огнетушитель не найден")

    record = ServiceRecord(
        fire_extinguisher_id=fe.id,
        created_at=datetime.now(timezone.utc),
        created_by=current_user.username,
    )
    _apply(record, data, fe, get_settings(db))
    db.add(record)
    sync_extinguisher_dates(db, fe)
    audit.log(db, request, current_user, audit.ACTION_CREATE,
              f"ТО огнетушителя {fe.inventory_number} от {record.service_date:%d.%m.%Y}: {_work_text(record)}",
              entity_type="service_record", entity_id=record.id,
              changes=audit.diff({}, audit.snapshot(record, AUDIT_FIELDS)))
    db.commit()
    db.refresh(record)
    recalculate_statuses(db, extinguisher_ids=[fe.id], keep_manual=[STATUS_DECOMMISSIONED])
    return record


@router.put("/{record_id}", response_model=ServiceRecordRead)
def update_service_record(
    record_id: int,
    data: ServiceRecordUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ROLE_ADMIN])),
):
    """
    Исправить запись о ТО (только администратор, с указанием причины).

    Args:
        record_id (int): ID записи.
        data (ServiceRecordUpdate): Новые значения и причина.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Администратор.

    Returns:
        ServiceRecord: Обновленная запись.
    """
    record = _get_or_404(db, record_id)
    fe = db.get(FireExtinguisher, record.fire_extinguisher_id)
    before = audit.snapshot(record, AUDIT_FIELDS)
    _apply(record, data, fe, get_settings(db))
    changes = audit.diff(before, audit.snapshot(record, AUDIT_FIELDS))
    if changes:
        sync_extinguisher_dates(db, fe)
        audit.log(db, request, current_user, audit.ACTION_UPDATE,
                  f"Исправлена запись о ТО огнетушителя {fe.inventory_number}. Причина: {data.reason.strip()}",
                  entity_type="service_record", entity_id=record.id, changes=changes)
    db.commit()
    db.refresh(record)
    if changes:
        recalculate_statuses(db, extinguisher_ids=[fe.id])
    return record


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service_record(
    record_id: int,
    request: Request,
    reason: str = Query(..., min_length=3, max_length=300, description="Причина удаления"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ROLE_ADMIN])),
):
    """
    Удалить ошибочную запись о ТО (только администратор, с указанием причины).

    Содержимое записи сохраняется в журнале действий.

    Args:
        record_id (int): ID записи.
        request (Request): Запрос (для журнала).
        reason (str): Причина удаления.
        db (Session): Сессия базы данных.
        current_user (User): Администратор.

    Returns:
        None
    """
    record = _get_or_404(db, record_id)
    fe = db.get(FireExtinguisher, record.fire_extinguisher_id)
    card = audit.snapshot(record, AUDIT_FIELDS)
    audit.log(db, request, current_user, audit.ACTION_DELETE,
              f"Удалена запись о ТО огнетушителя {fe.inventory_number} от "
              f"{record.service_date:%d.%m.%Y}. Причина: {reason.strip()}",
              entity_type="service_record", entity_id=record.id,
              changes={k: {"old": v, "new": None} for k, v in card.items()})
    db.delete(record)
    sync_extinguisher_dates(db, fe)
    db.commit()
    recalculate_statuses(db, extinguisher_ids=[fe.id])
