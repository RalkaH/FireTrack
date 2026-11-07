# inspections.py (v1.4)
"""
Модуль для управления процессом проверок огнетушителей.
Содержит маршруты для создания новых записей о проверках,
получения истории обслуживания, а также исправления ошибок.

Ошибочную проверку администратор исправляет или аннулирует с указанием
причины. Запись не удаляется: журнал должен оставаться полным, а все
действия видны в журнале действий.
"""

from datetime import datetime, timezone, date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

import audit
from app_settings import get_settings
from auth import EDITOR_ROLES, ROLE_ADMIN, get_current_active_user, require_role
from db import get_db
from deadlines import add_months
from models import Inspection, FireExtinguisher, Employee, User
from schemas import InspectionCreate, InspectionRead, InspectionReason, InspectionUpdate
from status_logic import STATUS_DECOMMISSIONED, recalculate_statuses

AUDIT_FIELDS = (
    "fire_extinguisher_id", "inspection_date", "employee_id", "pressure", "weight",
    "visual_inspection", "seal_condition", "safety_pin_condition",
    "hose_condition", "comments", "next_inspection_date",
)

router = APIRouter(
    prefix="/inspections",
    tags=["Inspections"],
    dependencies=[Depends(get_current_active_user)],
)


@router.post(
    "/",
    response_model=InspectionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_inspection(
    data: InspectionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(EDITOR_ROLES)),
):
    """
    Зарегистрировать новую проверку огнетушителя.
    Проверяет существование огнетушителя и сотрудника, сохраняет результаты
    проверки и пересчитывает статус огнетушителя по ее итогам.
    Если дата следующей проверки не указана, она рассчитывается по настройке
    ``inspection_interval_months`` (по умолчанию ежегодно, п. 5.1.1 ГОСТ Р 59641-2021).

    Статус списанного огнетушителя не меняется.

    Args:
        data (InspectionCreate): Данные для создания проверки.
        db (Session): Сессия базы данных.
        current_user (User): Пользователь с правами инженера или администратора.

    Returns:
        Inspection: Объект созданной проверки.

    Raises:
        HTTPException: Если не найден огнетушитель или сотрудник.
    """
    extinguisher = db.get(FireExtinguisher, data.fire_extinguisher_id)
    if extinguisher is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Огнетушитель не найден",
        )

    employee = db.get(Employee, data.employee_id)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сотрудник не найден",
        )

    next_inspection = data.next_inspection_date
    if next_inspection is None:
        next_inspection = add_months(
            data.inspection_date, int(get_settings(db)["inspection_interval_months"]))

    now = datetime.now(timezone.utc)
    insp = Inspection(
        fire_extinguisher_id=data.fire_extinguisher_id,
        inspection_date=data.inspection_date,
        employee_id=data.employee_id,
        pressure=data.pressure,
        weight=data.weight,
        visual_inspection=data.visual_inspection,
        seal_condition=data.seal_condition,
        safety_pin_condition=data.safety_pin_condition,
        hose_condition=data.hose_condition,
        comments=data.comments,
        next_inspection_date=next_inspection,
        created_at=now,
    )

    db.add(insp)
    extinguisher.updated_at = now
    db.flush()
    audit.log(db, request, current_user, audit.ACTION_CREATE,
              f"Проверка огнетушителя {extinguisher.inventory_number} "
              f"от {data.inspection_date:%d.%m.%Y} ({employee.full_name})",
              entity_type="inspection", entity_id=insp.id,
              changes=audit.diff({}, audit.snapshot(insp, AUDIT_FIELDS)))
    db.commit()
    db.refresh(insp)

    # Пересчитываем статус по итогам проверки (кроме списанных)
    recalculate_statuses(
        db,
        extinguisher_ids=[extinguisher.id],
        keep_manual=[STATUS_DECOMMISSIONED],
    )

    return insp


@router.get(
    "/by-extinguisher/{extinguisher_id}",
    response_model=List[InspectionRead],
)
def inspections_by_extinguisher(
    extinguisher_id: int,
    db: Session = Depends(get_db),
):
    """
    Получить историю всех проверок для заданного огнетушителя.
    Сортировка по убыванию даты проверки (новые сверху).

    Args:
        extinguisher_id (int): ID огнетушителя.
        db (Session): Сессия базы данных.

    Returns:
        List[Inspection]: Список записей о проверках.
    """
    return (
        db.query(Inspection)
        .filter(Inspection.fire_extinguisher_id == extinguisher_id)
        .order_by(Inspection.inspection_date.desc(), Inspection.id.desc())
        .all()
    )


@router.get("/", response_model=List[InspectionRead])
def list_inspections(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    include_annulled: bool = False,
    db: Session = Depends(get_db),
):
    """
    Получить общий журнал проверок всех огнетушителей.
    Позволяет фильтровать результаты по периоду дат.

    Args:
        date_from (Optional[date]): Фильтр "с даты" (включительно).
        date_to (Optional[date]): Фильтр "по дату" (включительно).
        include_annulled (bool): Показывать и аннулированные проверки.
        db (Session): Сессия базы данных.

    Returns:
        List[Inspection]: Отфильтрованный список проверок.
    """
    query = db.query(Inspection)
    if not include_annulled:
        query = query.filter(Inspection.annulled_at.is_(None))

    if date_from:
        query = query.filter(Inspection.inspection_date >= date_from)
    if date_to:
        query = query.filter(Inspection.inspection_date <= date_to)

    return query.order_by(Inspection.inspection_date.desc(), Inspection.id.desc()).all()


def _get_or_404(db: Session, inspection_id: int) -> Inspection:
    """Возвращает проверку или 404."""
    insp = db.get(Inspection, inspection_id)
    if insp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Проверка не найдена")
    return insp


def _inventory_number(db: Session, extinguisher_id: int) -> str:
    """Инвентарный номер огнетушителя для текста журнала."""
    fe = db.get(FireExtinguisher, extinguisher_id)
    return fe.inventory_number if fe else f"#{extinguisher_id}"


@router.put("/{inspection_id}", response_model=InspectionRead)
def update_inspection(
    inspection_id: int,
    data: InspectionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ROLE_ADMIN])),
):
    """
    Исправить ошибочную проверку (только администратор, с указанием причины).

    Args:
        inspection_id (int): ID проверки.
        data (InspectionUpdate): Изменяемые поля и причина.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Администратор.

    Returns:
        Inspection: Исправленная проверка.

    Raises:
        HTTPException: Проверка не найдена (404), аннулирована, ссылается на
            несуществующие объекты или даты противоречат друг другу (400).
    """
    insp = _get_or_404(db, inspection_id)
    if insp.annulled_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Аннулированную проверку нельзя исправить. Сначала восстановите ее")

    update = data.model_dump(exclude_unset=True, exclude={"reason"})
    for required in ("fire_extinguisher_id", "inspection_date", "employee_id", "next_inspection_date"):
        if required in update and update[required] is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Поле '{required}' не может быть пустым")
    if "fire_extinguisher_id" in update and db.get(FireExtinguisher, update["fire_extinguisher_id"]) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Огнетушитель не найден")
    if "employee_id" in update and db.get(Employee, update["employee_id"]) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Сотрудник не найден")

    inspection_date = update.get("inspection_date", insp.inspection_date)
    next_date = update.get("next_inspection_date", insp.next_inspection_date)
    if next_date < inspection_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Дата следующей проверки не может быть раньше даты проверки")

    old_extinguisher_id = insp.fire_extinguisher_id
    before = audit.snapshot(insp, AUDIT_FIELDS)
    for field, value in update.items():
        setattr(insp, field, value)
    changes = audit.diff(before, audit.snapshot(insp, AUDIT_FIELDS))
    if changes:
        audit.log(db, request, current_user, audit.ACTION_UPDATE,
                  f"Исправлена проверка огнетушителя {_inventory_number(db, insp.fire_extinguisher_id)} "
                  f"от {insp.inspection_date:%d.%m.%Y}. Причина: {data.reason.strip()}",
                  entity_type="inspection", entity_id=insp.id, changes=changes)
    db.commit()
    db.refresh(insp)
    if changes:
        recalculate_statuses(db, extinguisher_ids={old_extinguisher_id, insp.fire_extinguisher_id})
    return insp


@router.post("/{inspection_id}/annul", response_model=InspectionRead)
def annul_inspection(
    inspection_id: int,
    data: InspectionReason,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ROLE_ADMIN])),
):
    """
    Аннулировать ошибочную проверку (только администратор, с указанием причины).

    Запись остается в истории, но не участвует в статусах и отчетах.

    Args:
        inspection_id (int): ID проверки.
        data (InspectionReason): Причина.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Администратор.

    Returns:
        Inspection: Аннулированная проверка.

    Raises:
        HTTPException: Проверка не найдена (404) или уже аннулирована (400).
    """
    insp = _get_or_404(db, inspection_id)
    if insp.annulled_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Проверка уже аннулирована")
    reason = data.reason.strip()
    insp.annulled_at = datetime.now(timezone.utc)
    insp.annulled_by = current_user.username
    insp.annul_reason = reason
    audit.log(db, request, current_user, audit.ACTION_ANNUL,
              f"Аннулирована проверка огнетушителя {_inventory_number(db, insp.fire_extinguisher_id)} "
              f"от {insp.inspection_date:%d.%m.%Y}. Причина: {reason}",
              entity_type="inspection", entity_id=insp.id)
    db.commit()
    db.refresh(insp)
    recalculate_statuses(db, extinguisher_ids=[insp.fire_extinguisher_id])
    return insp


@router.post("/{inspection_id}/restore", response_model=InspectionRead)
def restore_inspection(
    inspection_id: int,
    data: InspectionReason,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ROLE_ADMIN])),
):
    """
    Восстановить аннулированную проверку (только администратор).

    Args:
        inspection_id (int): ID проверки.
        data (InspectionReason): Причина.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Администратор.

    Returns:
        Inspection: Восстановленная проверка.

    Raises:
        HTTPException: Проверка не найдена (404) или не аннулирована (400).
    """
    insp = _get_or_404(db, inspection_id)
    if insp.annulled_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Проверка не аннулирована")
    insp.annulled_at = None
    insp.annulled_by = None
    insp.annul_reason = None
    audit.log(db, request, current_user, audit.ACTION_RESTORE,
              f"Восстановлена проверка огнетушителя {_inventory_number(db, insp.fire_extinguisher_id)} "
              f"от {insp.inspection_date:%d.%m.%Y}. Причина: {data.reason.strip()}",
              entity_type="inspection", entity_id=insp.id)
    db.commit()
    db.refresh(insp)
    recalculate_statuses(db, extinguisher_ids=[insp.fire_extinguisher_id])
    return insp
