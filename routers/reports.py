# routers/reports.py (v1.5)
"""
Модуль генерации отчетов и аналитики.
Обеспечивает формирование статистики для дашборда, списков просроченного оборудования,
и выгрузку журналов проверок в форматах JSON и CSV.

Все сроки считаются по ПОСЛЕДНЕЙ проверке каждого огнетушителя, поэтому
старые записи журнала не попадают в «предстоящие» и не завышают счетчики.
Списанные огнетушители в предстоящие проверки не попадают.

Отчеты для печати (журнал проверок, журнал ТО и ремонта по форме А.2 и
карточки учета по форме А.1 ГОСТ Р 59641-2021, состояние парка) отдаются
в двух видах: XLSX-файлом и JSON для страницы печати ``/static/print.html``.
Данные для обоих готовит модуль ``report_data``. Аннулированные проверки
в журналы и выгрузки не попадают.
"""
import csv
from datetime import date, timedelta
from io import StringIO
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

import audit
import report_data
import xlsx_export
from app_settings import get_settings
from auth import get_current_active_user
from db import get_db
from export_utils import safe_cell
from deadlines import STATE_OVERDUE, STATE_SOON, compute_deadlines
from models import FireExtinguisher, Inspection, Location, Status, Employee, User
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
    query = db.query(Inspection).filter(Inspection.annulled_at.is_(None))
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


def _recharge_rows(db: Session) -> list:
    """
    Огнетушители, у которых перезарядка просрочена или скоро (в пределах
    ``recharge_warning_days`` из настроек). Списанные не учитываются.

    Args:
        db (Session): Сессия базы данных.

    Returns:
        list: Словари с номером, местом, сроком и состоянием, просроченные сверху.
    """
    settings = get_settings(db)
    today = date.today()
    decommissioned_id = status_ids_by_name(db).get(STATUS_DECOMMISSIONED)
    rows = (
        db.query(FireExtinguisher, Location)
        .join(Location, FireExtinguisher.location_id == Location.id)
        .all()
    )
    result = []
    for fe, loc in rows:
        if fe.status_id == decommissioned_id:
            continue
        d = compute_deadlines(fe, settings, today)
        if d["recharge_state"] not in (STATE_OVERDUE, STATE_SOON):
            continue
        result.append({
            "extinguisher_id": fe.id,
            "inventory_number": fe.inventory_number,
            "type": fe.type,
            "agent": d["agent_label"],
            "location": loc.name,
            "next_recharge": d["next_recharge_date"].isoformat(),
            "days_left": d["recharge_days_left"],
            "state": d["recharge_state"],
            "basis": d["recharge_basis"],
        })
    result.sort(key=lambda r: r["next_recharge"])
    return result


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
        .filter(Inspection.annulled_at.is_(None))
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
            [safe_cell(value) for value in (
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
            )]
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
    - Количество огнетушителей с просроченной и подходящей перезарядкой

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
    recharge = _recharge_rows(db)

    return {
        "total_extinguishers": total,
        "status_breakdown": status_breakdown,
        "expired_count": status_breakdown.get(STATUS_EXPIRED, 0),
        "upcoming_inspections_30_days": len(_upcoming_rows(db, 30)),
        "recharge_overdue_count": sum(1 for r in recharge if r["state"] == STATE_OVERDUE),
        "recharge_soon_count": sum(1 for r in recharge if r["state"] == STATE_SOON),
        "recharge_warning_days": get_settings(db)["recharge_warning_days"],
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


@router.get("/recharge")
def recharge_report(db: Session = Depends(get_db)):
    """
    Огнетушители с просроченной или подходящей перезарядкой (для дашборда).

    Returns:
        list: Список с датой перезарядки, остатком дней и состоянием
        (``overdue`` или ``soon``).
    """
    return _recharge_rows(db)


# ---------- Отчеты для печати ----------

def _xlsx_response(content: bytes, filename: str) -> Response:
    """Отдает XLSX-файл на скачивание."""
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _log_export(db: Session, request: Request, user: User, what: str) -> None:
    """Пишет выгрузку отчета в журнал действий."""
    audit.log(db, request, user, audit.ACTION_EXPORT, f"Выгрузка отчета: {what}",
              entity_type="report", commit=True)


def _period_suffix(date_from: Optional[date], date_to: Optional[date]) -> str:
    """Часть имени файла с периодом."""
    if date_from or date_to:
        return f"{date_from or 'start'}_{date_to or 'today'}"
    return date.today().isoformat()


@router.get("/print/journal")
def print_journal(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """
    Журнал проверок за период для страницы печати.

    Returns:
        dict: ``header`` (организация, ответственный), ``period`` и ``rows``.
    """
    return {"header": report_data.report_header(db),
            "period": report_data.period_label(date_from, date_to),
            "rows": report_data.journal_rows(db, date_from, date_to)}


@router.get("/print/maintenance")
def print_maintenance(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """
    Журнал ТО и ремонта по форме А.2 ГОСТ Р 59641-2021 для страницы печати.

    Returns:
        dict: ``header``, ``period`` и ``rows``.
    """
    return {"header": report_data.report_header(db),
            "period": report_data.period_label(date_from, date_to),
            "rows": report_data.maintenance_rows(db, date_from, date_to)}


@router.get("/print/fleet")
def print_fleet(
    days: int = Query(30, ge=1, le=365, description="Горизонт ближайших проверок, дней"),
    db: Session = Depends(get_db),
):
    """
    Отчет «Состояние парка» для страницы печати.

    Returns:
        dict: ``header`` и ``summary``.
    """
    return {"header": report_data.report_header(db),
            "summary": report_data.fleet_summary(db, horizon_days=days)}


@router.get("/journal.xlsx")
def journal_xlsx(
    request: Request,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Журнал проверок за период в Excel (оформлен для печати).

    Returns:
        Response: Файл XLSX.
    """
    period = report_data.period_label(date_from, date_to)
    content = xlsx_export.journal_workbook(
        report_data.journal_rows(db, date_from, date_to), report_data.report_header(db), period)
    _log_export(db, request, current_user, f"журнал проверок XLSX ({period})")
    return _xlsx_response(content, f"journal_{_period_suffix(date_from, date_to)}.xlsx")


@router.get("/maintenance.xlsx")
def maintenance_xlsx(
    request: Request,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Журнал ТО и ремонта (форма А.2 ГОСТ Р 59641-2021) в Excel.

    Returns:
        Response: Файл XLSX.
    """
    period = report_data.period_label(date_from, date_to)
    content = xlsx_export.maintenance_workbook(
        report_data.maintenance_rows(db, date_from, date_to), report_data.report_header(db), period)
    _log_export(db, request, current_user, f"журнал ТО XLSX ({period})")
    return _xlsx_response(content, f"maintenance_{_period_suffix(date_from, date_to)}.xlsx")


@router.get("/fleet.xlsx")
def fleet_xlsx(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Отчет «Состояние парка» в Excel (несколько листов).

    Returns:
        Response: Файл XLSX.
    """
    content = xlsx_export.fleet_workbook(
        report_data.fleet_summary(db, horizon_days=days), report_data.report_header(db))
    _log_export(db, request, current_user, "состояние парка XLSX")
    return _xlsx_response(content, f"fleet_{date.today().isoformat()}.xlsx")


@router.get("/print/cards")
def print_cards(
    extinguisher_id: Optional[int] = Query(None, description="Один огнетушитель. Пусто: все, кроме списанных"),
    db: Session = Depends(get_db),
):
    """
    Карточки учета по форме А.1 ГОСТ Р 59641-2021 для страницы печати.

    Returns:
        dict: ``header`` и ``cards``.
    """
    return {"header": report_data.report_header(db),
            "cards": report_data.card_rows(db, extinguisher_id)}


@router.get("/cards.xlsx")
def cards_xlsx(
    request: Request,
    extinguisher_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Карточки учета по форме А.1 ГОСТ Р 59641-2021 в Excel.

    Returns:
        Response: Файл XLSX.
    """
    content = xlsx_export.cards_workbook(
        report_data.card_rows(db, extinguisher_id), report_data.report_header(db))
    _log_export(db, request, current_user, "карточки учета XLSX")
    return _xlsx_response(content, f"cards_{date.today().isoformat()}.xlsx")
