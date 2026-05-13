# inspections.py (v1.1)
"""
Модуль для управления процессом проверок огнетушителей.
Содержит маршруты для создания новых записей о проверках,
а также получения истории обслуживания оборудования.
"""

from datetime import datetime, timezone, date, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db import get_db
from models import Inspection, FireExtinguisher, Employee, Status
from schemas import InspectionCreate, InspectionRead

router = APIRouter(
    prefix="/inspections",
    tags=["Inspections"],
)


@router.post(
    "/",
    response_model=InspectionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_inspection(
    data: InspectionCreate,
    db: Session = Depends(get_db),
):
    """
    Зарегистрировать новую проверку огнетушителя.
    Проверяет существование огнетушителя и сотрудника,
    сохраняет результаты проверки и обновляет время изменения огнетушителя.
    Автоматически рассчитывает дату следующей проверки (через 180 дней), если она не указана.

    Args:
        data (InspectionCreate): Данные для создания проверки.
        db (Session): Сессия базы данных.

    Returns:
        Inspection: Объект созданной проверки.

    Raises:
        HTTPException: Если дата из будущего, либо не найден огнетушитель/сотрудник.
    """
    # Валидация даты проверки (не из будущего)
    if data.inspection_date > date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дата проверки не может быть из будущего",
        )

    # Проверяем, что огнетушитель существует
    extinguisher = db.query(FireExtinguisher).get(data.fire_extinguisher_id)
    if extinguisher is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Огнетушитель не найден",
        )

    # Проверяем, что сотрудник существует
    employee = db.query(Employee).get(data.employee_id)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сотрудник не найден",
        )

    # Если не указана дата следующей проверки, рассчитываем автоматически
    # По ГОСТ проверка каждые 6 месяцев
    next_inspection = data.next_inspection_date
    if next_inspection is None:
        next_inspection = data.inspection_date + timedelta(days=180)

    # Создаём запись о проверке
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
        created_at=datetime.now(timezone.utc),
    )

    db.add(insp)

    # Обновляем у огнетушителя дату последнего изменения
    extinguisher.updated_at = datetime.now(timezone.utc)

    # Автоматически пересчитываем статус
    status_actual = db.query(Status).filter(Status.name == "Актуально").first()
    if status_actual:
        extinguisher.status_id = status_actual.id

    db.commit()
    db.refresh(insp)

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
        .order_by(Inspection.inspection_date.desc())
        .all()
    )


@router.get("/", response_model=List[InspectionRead])
def list_inspections(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
):
    """
    Получить общий журнал проверок всех огнетушителей.
    Позволяет фильтровать результаты по периоду дат.

    Args:
        date_from (date | None): Фильтр "с даты" (включительно).
        date_to (date | None): Фильтр "по дату" (включительно).
        db (Session): Сессия базы данных.

    Returns:
        List[Inspection]: Отфильтрованный список проверок.
    """
    query = db.query(Inspection)

    if date_from:
        query = query.filter(Inspection.inspection_date >= date_from)
    if date_to:
        query = query.filter(Inspection.inspection_date <= date_to)

    return query.order_by(Inspection.inspection_date.desc()).all()
