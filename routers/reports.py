# routers/reports.py (v1.1)
from datetime import date
from io import StringIO
import csv
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from db import get_db
from models import FireExtinguisher, Inspection, Location, Status, Employee
from schemas import InspectionRead


router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
)


@router.get("/journal", response_model=List[InspectionRead])
def journal_json(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """
    Журнал проверок за период в формате JSON.
    Если даты не указаны, возвращаются все проверки.
    """
    query = db.query(Inspection)

    if date_from is not None:
        query = query.filter(Inspection.inspection_date >= date_from)
    if date_to is not None:
        query = query.filter(Inspection.inspection_date <= date_to)

    query = query.order_by(Inspection.inspection_date.desc())
    return query.all()


@router.get("/journal.csv")
def journal_csv(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """
    Журнал проверок за период в формате CSV для Excel.
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

    query = query.order_by(Inspection.inspection_date.desc())

    # Собираем CSV в памяти
    output = StringIO()
    writer = csv.writer(output, delimiter=";")

    # Заголовок как в журнале
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
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/expired")
def expired_list(db: Session = Depends(get_db)):
    """
    Список просроченных огнетушителей (по текущему статусу).
    """
    expired_status = db.query(Status).filter(
        Status.name == "Просрочено").first()
    if expired_status is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Статус 'Просрочено' не найден",
        )

    extinguishers = (
        db.query(FireExtinguisher, Location)
        .join(Location, FireExtinguisher.location_id == Location.id)
        .filter(FireExtinguisher.status_id == expired_status.id)
        .all()
    )

    return [
        {
            "id": fe.id,
            "inventory_number": fe.inventory_number,
            "type": fe.type,
            "location": loc.name,
        }
        for fe, loc in extinguishers
    ]


@router.get("/dashboard")
def dashboard_statistics(db: Session = Depends(get_db)):
    """
    Получить статистику для дашборда:
    - Общее количество огнетушителей
    - Количество по статусам
    - Количество просроченных
    - Количество требующих проверки в ближайшие 30 дней
    """
    from datetime import timedelta

    total = db.query(FireExtinguisher).count()

    # Статистика по статусам
    status_stats = (
        db.query(Status.name, func.count(FireExtinguisher.id))
        .join(FireExtinguisher, Status.id == FireExtinguisher.status_id)
        .group_by(Status.name)
        .all()
    )
    # Преобразуем в обычный словарь {status_name: count}
    status_breakdown = {row[0]: int(row[1]) for row in status_stats}

    # Огнетушители, требующие проверки в течение 30 дней
    today = date.today()
    upcoming_deadline = today + timedelta(days=30)

    upcoming_inspections = (
        db.query(func.count(FireExtinguisher.id))
        .join(Inspection, FireExtinguisher.id == Inspection.fire_extinguisher_id)
        .filter(
            Inspection.next_inspection_date.between(today, upcoming_deadline)
        )
        .scalar()
        or 0
    )

    # Просроченные
    expired_status = db.query(Status).filter(
        Status.name == "Просрочено").first()
    expired_count = 0
    if expired_status is not None:
        expired_count = (
            db.query(FireExtinguisher)
            .filter(FireExtinguisher.status_id == expired_status.id)
            .count()
        )

    return {
        "total_extinguishers": total,
        "status_breakdown": status_breakdown,
        "expired_count": expired_count,
        "upcoming_inspections_30_days": upcoming_inspections,
    }


@router.get("/upcoming-inspections")
def upcoming_inspections_report(
    days: int = Query(30, ge=1, le=365,
                      description="Количество дней для прогноза"),
    db: Session = Depends(get_db),
):
    """
    Список огнетушителей, которые требуют проверки в ближайшие N дней.
    """
    from datetime import timedelta

    today = date.today()
    deadline = today + timedelta(days=days)

    # Подзапрос для получения последней проверки каждого огнетушителя
    latest_inspections = (
        db.query(
            Inspection.fire_extinguisher_id,
            func.max(Inspection.inspection_date).label("last_date"),
        )
        .group_by(Inspection.fire_extinguisher_id)
        .subquery()
    )

    # Основной запрос
    results = (
        db.query(
            FireExtinguisher,
            Inspection,
            Location,
        )
        .join(
            latest_inspections,
            FireExtinguisher.id == latest_inspections.c.fire_extinguisher_id,
        )
        .join(
            Inspection,
            (Inspection.fire_extinguisher_id == FireExtinguisher.id)
            & (Inspection.inspection_date == latest_inspections.c.last_date),
        )
        .join(Location, FireExtinguisher.location_id == Location.id)
        .filter(
            Inspection.next_inspection_date.between(today, deadline)
        )
        .order_by(Inspection.next_inspection_date)
        .all()
    )

    return [
        {
            "extinguisher_id": fe.id,
            "inventory_number": fe.inventory_number,
            "type": fe.type,
            "location": loc.name,
            "last_inspection": insp.inspection_date.isoformat(),
            "next_inspection": insp.next_inspection_date.isoformat(),
            "days_until_inspection": (insp.next_inspection_date - today).days,
        }
        for fe, insp, loc in results
    ]


@router.get("/upcoming")
def upcoming_inspections(days: int = 30, db: Session = Depends(get_db)):
    from datetime import date, timedelta

    today = date.today()
    limit_date = today + timedelta(days=days)

    query = (
        db.query(Inspection, FireExtinguisher, Location)
        .join(FireExtinguisher, Inspection.fire_extinguisher_id == FireExtinguisher.id)
        .join(Location, FireExtinguisher.location_id == Location.id)
        .filter(Inspection.next_inspection_date >= today)
        .filter(Inspection.next_inspection_date <= limit_date)
        .order_by(Inspection.next_inspection_date.asc())
    )

    result = []
    for insp, fe, loc in query.all():
        days_left = (insp.next_inspection_date - today).days
        result.append(
            {
                "inventory_number": fe.inventory_number,
                "location": loc.name,
                "next_inspection": insp.next_inspection_date.isoformat(),
                "days_until_inspection": days_left,
            }
        )

    return result


@router.get("/journal.json", response_model=list[InspectionRead])
def export_journal_json(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Inspection)
    if date_from:
        q = q.filter(Inspection.inspection_date >= date_from)
    if date_to:
        q = q.filter(Inspection.inspection_date <= date_to)
    return q.order_by(Inspection.inspection_date).all()
