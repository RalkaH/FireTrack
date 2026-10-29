# inspections.py (v1.2)
"""
Модуль для управления процессом проверок огнетушителей.
Содержит маршруты для создания новых записей о проверках,
а также получения истории обслуживания оборудования.
"""

from datetime import datetime, timezone, date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import EDITOR_ROLES, get_current_active_user, require_role
from db import get_db
from models import Inspection, FireExtinguisher, Employee, User
from schemas import InspectionCreate, InspectionRead
from status_logic import STATUS_DECOMMISSIONED, recalculate_statuses

# Периодичность плановой проверки по умолчанию (около 6 месяцев)
DEFAULT_INSPECTION_INTERVAL_DAYS = 180

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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(EDITOR_ROLES)),
):
    """
    Зарегистрировать новую проверку огнетушителя.
    Проверяет существование огнетушителя и сотрудника, сохраняет результаты
    проверки и пересчитывает статус огнетушителя по ее итогам.
    Если дата следующей проверки не указана, она рассчитывается автоматически
    (через 180 дней).

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
        next_inspection = data.inspection_date + timedelta(
            days=DEFAULT_INSPECTION_INTERVAL_DAYS)

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
    db: Session = Depends(get_db),
):
    """
    Получить общий журнал проверок всех огнетушителей.
    Позволяет фильтровать результаты по периоду дат.

    Args:
        date_from (Optional[date]): Фильтр "с даты" (включительно).
        date_to (Optional[date]): Фильтр "по дату" (включительно).
        db (Session): Сессия базы данных.

    Returns:
        List[Inspection]: Отфильтрованный список проверок.
    """
    query = db.query(Inspection)

    if date_from:
        query = query.filter(Inspection.inspection_date >= date_from)
    if date_to:
        query = query.filter(Inspection.inspection_date <= date_to)

    return query.order_by(Inspection.inspection_date.desc(), Inspection.id.desc()).all()
