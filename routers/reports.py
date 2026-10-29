# routers/reports.py (v1.3)
"""
Модуль генерации отчетов и аналитики.
Обеспечивает формирование статистики для дашборда, списков просроченного оборудования,
и выгрузку журналов проверок в форматах JSON и CSV.

Все сроки считаются по ПОСЛЕДНЕЙ проверке каждого огнетушителя, поэтому
старые записи журнала не попадают в «предстоящие» и не завышают счетчики.
Списанные огнетушители в предстоящие проверки не попадают.
"""
import csv
from datetime import date, timedelta
from io import StringIO
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_active_user
from db import get_db
from models import FireExtinguisher, Inspection, Location, Status, Employee
from schemas import InspectionRead
from status_logic import (
    STATUS_DECOMMISSIONED,
    STATUS_EXPIRED,
    latest_inspections_subquery,
    status_ids_by_name,
)


router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
    dependencies=[Depends(get_current_active_user)],
)


def _filtered_journal(db: Session, date_from: Optional[date], date_to: Optional[date]):
    """Общий запрос журнала проверок с фильтром по периоду."""
    query = db.query(Inspection)
    if date_from is not None:
        query = query.filter(Inspection.inspection_date >= date_from)
    if date_to is not None:
        query = query.filter(Inspection.inspection_date <= date_to)
    return query


def _upcoming_rows(db: Session, days: int):
    """
    Огнетушители, у которых плановая проверка наступает в ближайшие N дней.

    Args:
        db (Session): Сессия базы данных.
        days (int): Горизонт в днях.

    Returns:
        list: Кортежи (FireExtinguisher, Location, last_date, next_date).
    """
    today = date.today()
    deadline = today + timedelta(days=days)
    latest = latest_inspections_subquery(db)

    query = (
        db.query(
            FireExtinguisher,
            Location,
            latest.c.inspection_date,
            latest.c.next_inspection_date,
        )
        .join(latest, FireExtinguisher.id == latest.c.fire_extinguisher_id)
        .join(Location, FireExtinguisher.location_id == Location.id)
        .filter(latest.c.next_inspection_date.between(today, deadline))
    )

    decommissioned_id = status_ids_by_name(db).get(STATUS_DECOMMISSIONED)
    if decommissioned_id is not None:
        query = query.filter(FireExtinguisher.status_id != decommissioned_id)

    return query.order_by(latest.c.next_inspection_date).all()


@router.get("/journal", response_model=List[InspectionRead])
def journal_json(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """
    Получить электронный журнал проверок за выбранный период в формате JSON.
    Если даты не указаны, возвращается история всех проверок.

    Args:
        date_from (Optional[date]): Начальная дата фильтра.
        date_to (Optional[date]): Конечная дата фильтра.
        db (Session): Сессия базы данных.

    Returns:
        List[Inspection]: Список записей журнала.
    """
    query = _filtered_journal(db, date_from, date_to)
    return query.order_by(Inspection.inspection_date.desc(), Inspection.id.desc()).all()


@router.get("/journal.csv")
def journal_csv(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """
    Сгенерировать и скачать журнал проверок за период в формате CSV (совместимо с Excel).
    Файл сохраняется в UTF-8 с BOM, поэтому Excel корректно открывает кириллицу.

    Args:
        date_from (Optional[date]): Начальная дата фильтра.
        date_to (Optional[date]): Конечная дата фильтра.
        db (Session): Сессия базы данных.

    Returns:
        StreamingResponse: Файл CSV, готовый для скачивания браузером.
    """
    query = (
        db.query(Inspection, FireExtinguisher, Location, Status, Employee)
        .join(FireExtinguisher, Inspection.fire_extinguisher_id == FireExtinguisher.id)
        .join(Location, FireExtinguisher.location_id == Location.id)
        .join(Status, FireExtinguisher.status_id == Status.id)
        .join(Employee, Inspection.employee_id == Employee.id)
    )

    if date_from is not None:
        query = query.filter(Inspection.inspection_date >= date_from)
    if date_to is not None:
        query = query.filter(Inspection.inspection_date <= date_to)

    query = query.order_by(Inspection.inspection_date.desc(), Inspection.id.desc())

    output = StringIO()
    output.write("﻿")  # BOM для Excel
    writer = csv.writer(output, delimiter=";")

    # Заголовок совпадает с форматом импорта журнала
    writer.writerow(
        [
            "Дата проверки",
            "Инвентарный номер",
            "Тип",
            "Место расположения",
            "Статус",
            "ФИО проверяющего",
            "Должность",
            "Давление",
            "Вес",
            "Визуальный осмотр",
            "Состояние пломбы",
            "Состояние чеки",
            "Состояние шланга",
            "Комментарии",
            "Дата следующей проверки",
        ]
    )

    for insp, fe, loc, st, emp in query.all():
        writer.writerow(
            [
                insp.inspection_date.isoformat(),
                fe.inventory_number,
                fe.type,
                loc.name,
                st.name,
                emp.full_name,
                emp.position,
                insp.pressure,
                insp.weight,
                insp.visual_inspection,
                insp.seal_condition,
                insp.safety_pin_condition,
                insp.hose_condition,
                insp.comments,
                insp.next_inspection_date.isoformat(),
            ]
        )

    output.seek(0)
    filename = f"journal_{date.today().isoformat()}.csv"
    return StreamingResponse(
        output,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/expired")
def expired_list(db: Session = Depends(get_db)):
    """
    Получить сводный список просроченных огнетушителей (в статусе 'Просрочено').
    Для каждого указывается дата, когда должна была пройти проверка,
    и количество дней просрочки (если проверки вообще были).

    Args:
        db (Session): Сессия базы данных.

    Returns:
        list: Список словарей с краткой информацией о просроченном оборудовании.

    Raises:
        HTTPException: Если системный статус "Просрочено" не заведен в базу.
    """
    expired_status_id = status_ids_by_name(db).get(STATUS_EXPIRED)
    if expired_status_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Статус 'Просрочено' не найден",
        )

    latest = latest_inspections_subquery(db)
    rows = (
        db.query(FireExtinguisher, Location, latest.c.next_inspection_date)
        .join(Location, FireExtinguisher.location_id == Location.id)
        .outerjoin(latest, FireExtinguisher.id == latest.c.fire_extinguisher_id)
        .filter(FireExtinguisher.status_id == expired_status_id)
        .order_by(latest.c.next_inspection_date.asc().nullsfirst())
        .all()
    )

    today = date.today()
    return [
        {
            "id": fe.id,
            "inventory_number": fe.inventory_number,
            "type": fe.type,
            "location": loc.name,
            "due_date": next_date.isoformat() if next_date else None,
            "days_overdue": (today - next_date).days if next_date else None,
        }
        for fe, loc, next_date in rows
    ]


@router.get("/dashboard")
def dashboard_statistics(db: Session = Depends(get_db)):
    """
    Сформировать агрегированную статистику для вывода на главной панели (Dashboard).

    Аналитика включает:
    - Общее количество инвентаря
    - Разбивка по текущим статусам
    - Количество огнетушителей, которым проверка нужна в ближайшие 30 дней
    - Общее количество просроченного оборудования

    Args:
        db (Session): Сессия базы данных.

    Returns:
        dict: Набор метрик для дашборда.
    """
    total = db.query(FireExtinguisher).count()

    status_stats = (
        db.query(Status.name, func.count(FireExtinguisher.id))
        .join(FireExtinguisher, Status.id == FireExtinguisher.status_id)
        .group_by(Status.name)
        .all()
    )
    status_breakdown = {row[0]: int(row[1]) for row in status_stats}

    return {
        "total_extinguishers": total,
        "status_breakdown": status_breakdown,
        "expired_count": status_breakdown.get(STATUS_EXPIRED, 0),
        "upcoming_inspections_30_days": len(_upcoming_rows(db, 30)),
    }


@router.get("/upcoming-inspections")
def upcoming_inspections_report(
    days: int = Query(30, ge=1, le=365,
                      description="Количество дней для прогноза"),
    db: Session = Depends(get_db),
):
    """
    Детальный список огнетушителей, для которых плановое обслуживание (ТО)
    наступает в ближайшие N дней. Учитывается только последняя проверка.

    Args:
        days (int): Горизонт прогнозирования в днях.
        db (Session): Сессия базы данных.

    Returns:
        list: Список оборудования, ожидающего проверку.
    """
    today = date.today()
    return [
        {
            "extinguisher_id": fe.id,
            "inventory_number": fe.inventory_number,
            "type": fe.type,
            "location": loc.name,
            "last_inspection": last_date.isoformat(),
            "next_inspection": next_date.isoformat(),
            "days_until_inspection": (next_date - today).days,
        }
        for fe, loc, last_date, next_date in _upcoming_rows(db, days)
    ]


@router.get("/upcoming")
def upcoming_inspections(
    days: int = Query(30, ge=1, le=365, description="Количество дней"),
    db: Session = Depends(get_db),
):
    """
    Упрощенный список предстоящих проверок (используется дашбордом).
    Учитывается только последняя проверка каждого огнетушителя.

    Args:
        days (int): Количество дней.
        db (Session): Сессия базы данных.

    Returns:
        list: Краткая информация о предстоящих проверках.
    """
    today = date.today()
    return [
        {
            "extinguisher_id": fe.id,
            "inventory_number": fe.inventory_number,
            "location": loc.name,
            "next_inspection": next_date.isoformat(),
            "days_until_inspection": (next_date - today).days,
        }
        for fe, loc, _last_date, next_date in _upcoming_rows(db, days)
    ]


@router.get("/journal.json", response_model=List[InspectionRead])
def export_journal_json(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """
    Альтернативный эндпоинт для экспорта журнала проверок в формате JSON
    (в хронологическом порядке).

    Args:
        date_from (Optional[date]): Дата с.
        date_to (Optional[date]): Дата по.
        db (Session): Сессия базы данных.

    Returns:
        list[Inspection]: Отфильтрованный журнал.
    """
    query = _filtered_journal(db, date_from, date_to)
    return query.order_by(Inspection.inspection_date, Inspection.id).all()
