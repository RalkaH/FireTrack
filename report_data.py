# report_data.py (v1.0)
"""
Данные для отчетов.

Каждая функция возвращает готовые строки (словари), из которых потом
строятся XLSX-файл (``xlsx_export``) и страница для печати
(``static/print.html``). Так оба формата всегда показывают одно и то же.

Отчеты:

1. :func:`journal_rows` — журнал проверок за период.
2. :func:`maintenance_rows` — журнал технического обслуживания огнетушителей
   по рекомендуемой форме Г.2 приложения Г СП 9.13130.2009.
3. :func:`fleet_summary` — состояние парка: сводка по статусам и местам,
   проблемные огнетушители, ближайшие проверки, перезарядки и сроки службы.
"""
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app_settings import get_settings
from deadlines import STATE_OVERDUE, STATE_SOON, compute_deadlines
from models import Employee, FireExtinguisher, Inspection, Location, Status
from status_logic import (
    DEFECT_VALUES,
    STATUS_DECOMMISSIONED,
    STATUS_EXPIRED,
    STATUS_NEEDS_SERVICE,
    latest_inspections_subquery,
)


def period_label(date_from: Optional[date], date_to: Optional[date]) -> str:
    """Подпись периода для шапки отчета."""
    if date_from and date_to:
        return f"с {date_from:%d.%m.%Y} по {date_to:%d.%m.%Y}"
    if date_from:
        return f"с {date_from:%d.%m.%Y}"
    if date_to:
        return f"по {date_to:%d.%m.%Y}"
    return "за все время"


def report_header(db: Session) -> Dict[str, str]:
    """Название организации и ответственный из настроек."""
    s = get_settings(db)
    return {
        "organization_name": s["organization_name"],
        "responsible_position": s["responsible_position"],
        "responsible_name": s["responsible_name"],
    }


def _journal_query(db: Session, date_from: Optional[date], date_to: Optional[date]):
    """Проверки с огнетушителем, местом и сотрудником за период."""
    query = (
        db.query(Inspection, FireExtinguisher, Location, Employee)
        .join(FireExtinguisher, Inspection.fire_extinguisher_id == FireExtinguisher.id)
        .join(Location, FireExtinguisher.location_id == Location.id)
        .join(Employee, Inspection.employee_id == Employee.id)
    )
    if date_from is not None:
        query = query.filter(Inspection.inspection_date >= date_from)
    if date_to is not None:
        query = query.filter(Inspection.inspection_date <= date_to)
    return query.order_by(Inspection.inspection_date, FireExtinguisher.inventory_number, Inspection.id)


def defects_text(insp: Inspection) -> str:
    """Список найденных дефектов одной строкой."""
    parts = []
    for label, value in (("осмотр", insp.visual_inspection), ("пломба", insp.seal_condition),
                         ("чека", insp.safety_pin_condition), ("шланг", insp.hose_condition)):
        if (value or "").strip() in DEFECT_VALUES:
            parts.append(f"{label}: {value.strip().lower()}")
    return "; ".join(parts)


def journal_rows(db: Session, date_from: Optional[date], date_to: Optional[date]) -> List[Dict[str, Any]]:
    """
    Журнал проверок за период (старые сверху, как в бумажном журнале).

    Args:
        db (Session): Сессия базы данных.
        date_from (Optional[date]): Начало периода.
        date_to (Optional[date]): Конец периода.

    Returns:
        List[Dict[str, Any]]: Строки журнала.
    """
    rows = []
    for n, (insp, fe, loc, emp) in enumerate(_journal_query(db, date_from, date_to).all(), start=1):
        rows.append({
            "n": n,
            "inspection_date": insp.inspection_date,
            "inventory_number": fe.inventory_number,
            "type": fe.type,
            "location": loc.name,
            "pressure": insp.pressure,
            "weight": insp.weight,
            "visual_inspection": insp.visual_inspection,
            "seal_condition": insp.seal_condition,
            "safety_pin_condition": insp.safety_pin_condition,
            "hose_condition": insp.hose_condition,
            "defects": defects_text(insp),
            "comments": insp.comments,
            "next_inspection_date": insp.next_inspection_date,
            "employee": emp.full_name,
            "employee_position": emp.position,
        })
    return rows


def maintenance_rows(db: Session, date_from: Optional[date], date_to: Optional[date]) -> List[Dict[str, Any]]:
    """
    Журнал ТО огнетушителей по форме Г.2 СП 9.13130.2009.

    Колонки формы: «№ и марка огнетушителя», «Техническое обслуживание
    (вид и дата)» с подколонками «Проверка узлов огнетушителя», «Проверка
    качества ОТВ», «Проверка индикатора давления», «Перезарядка
    огнетушителя», «Испытание узлов огнетушителя», затем «Замечания
    о техническом состоянии», «Принятые меры» и «Должность, фамилия,
    инициалы и подпись ответственного лица».

    Каждая проверка из журнала дает строку: осмотр узлов (дата), масса
    в колонке качества ОТВ, давление в колонке индикатора. Перезарядки
    за период добавляются отдельными строками по дате последней
    перезарядки. «Принятые меры» и подпись заполняются от руки.

    Args:
        db (Session): Сессия базы данных.
        date_from (Optional[date]): Начало периода.
        date_to (Optional[date]): Конец периода.

    Returns:
        List[Dict[str, Any]]: Строки журнала в порядке дат.
    """
    rows: List[Dict[str, Any]] = []
    for insp, fe, _loc, emp in _journal_query(db, date_from, date_to).all():
        day = f"{insp.inspection_date:%d.%m.%Y}"
        remarks = [r for r in (defects_text(insp), (insp.comments or "").strip()) if r]
        rows.append({
            "date": insp.inspection_date,
            "extinguisher": f"{fe.inventory_number}, {fe.type}",
            "units_check": f"{day}, осмотр",
            "agent_check": f"{day}, масса {insp.weight:g} кг" if insp.weight is not None else "",
            "pressure_check": f"{day}, {insp.pressure:g} МПа" if insp.pressure is not None else "",
            "recharge": "",
            "units_test": "",
            "remarks": "; ".join(remarks) or "Замечаний нет",
            "measures": "",
            "responsible": f"{emp.position}, {emp.full_name}",
        })

    recharge_query = db.query(FireExtinguisher).filter(FireExtinguisher.last_recharge_date.isnot(None))
    if date_from is not None:
        recharge_query = recharge_query.filter(FireExtinguisher.last_recharge_date >= date_from)
    if date_to is not None:
        recharge_query = recharge_query.filter(FireExtinguisher.last_recharge_date <= date_to)
    for fe in recharge_query.all():
        rows.append({
            "date": fe.last_recharge_date,
            "extinguisher": f"{fe.inventory_number}, {fe.type}",
            "units_check": "",
            "agent_check": "",
            "pressure_check": "",
            "recharge": f"{fe.last_recharge_date:%d.%m.%Y}",
            "units_test": "",
            "remarks": "",
            "measures": "",
            "responsible": "",
        })

    rows.sort(key=lambda r: (r["date"], r["extinguisher"]))
    for n, row in enumerate(rows, start=1):
        row["n"] = n
    return rows


def fleet_summary(db: Session, today: Optional[date] = None, horizon_days: int = 30) -> Dict[str, Any]:
    """
    Отчет «Состояние парка».

    Args:
        db (Session): Сессия базы данных.
        today (Optional[date]): Дата отчета.
        horizon_days (int): Горизонт для ближайших проверок, дней.

    Returns:
        Dict[str, Any]: Сводка и списки:
        ``by_status``, ``by_location``, ``problems`` (просрочено и требует
        обслуживания), ``upcoming_inspections``, ``recharge`` (просрочено
        и скоро), ``service_life`` (истек и скоро истекает).
    """
    today = today or date.today()
    settings = get_settings(db)
    latest = latest_inspections_subquery(db)
    rows = (
        db.query(FireExtinguisher, Location, Status, latest.c.inspection_date, latest.c.next_inspection_date)
        .join(Location, FireExtinguisher.location_id == Location.id)
        .join(Status, FireExtinguisher.status_id == Status.id)
        .outerjoin(latest, FireExtinguisher.id == latest.c.fire_extinguisher_id)
        .order_by(FireExtinguisher.inventory_number)
        .all()
    )

    by_status: Dict[str, int] = {}
    by_location: Dict[str, Dict[str, int]] = {}
    problems, upcoming, recharge, service = [], [], [], []
    horizon = today + timedelta(days=horizon_days)

    for fe, loc, st, last_date, next_date in rows:
        by_status[st.name] = by_status.get(st.name, 0) + 1
        loc_stat = by_location.setdefault(loc.name, {"total": 0, "problems": 0})
        loc_stat["total"] += 1
        if st.name == STATUS_DECOMMISSIONED:
            continue

        d = compute_deadlines(fe, settings, today)
        base = {"id": fe.id, "inventory_number": fe.inventory_number, "type": fe.type,
                "location": loc.name, "status": st.name}

        if st.name in (STATUS_EXPIRED, STATUS_NEEDS_SERVICE):
            loc_stat["problems"] += 1
            problems.append({**base, "last_inspection": last_date, "next_inspection": next_date,
                             "days_overdue": (today - next_date).days if next_date and next_date < today else None})
        if next_date and today <= next_date <= horizon:
            upcoming.append({**base, "next_inspection": next_date, "days_left": (next_date - today).days})
        if d["recharge_state"] in (STATE_OVERDUE, STATE_SOON):
            recharge.append({**base, "next_recharge": d["next_recharge_date"],
                             "days_left": d["recharge_days_left"], "state": d["recharge_state"],
                             "agent": d["agent_label"], "basis": d["recharge_basis"]})
        if d["service_state"] in (STATE_OVERDUE, STATE_SOON):
            service.append({**base, "service_end": d["service_end_date"],
                            "days_left": d["service_days_left"], "state": d["service_state"]})

    upcoming.sort(key=lambda r: r["next_inspection"])
    recharge.sort(key=lambda r: r["next_recharge"])
    service.sort(key=lambda r: r["service_end"])
    problems.sort(key=lambda r: (r["next_inspection"] or date.min, r["inventory_number"]))

    return {
        "date": today,
        "total": len(rows),
        "by_status": by_status,
        "by_location": [{"location": k, **v} for k, v in sorted(by_location.items())],
        "problems": problems,
        "upcoming_inspections": upcoming,
        "horizon_days": horizon_days,
        "recharge": recharge,
        "recharge_warning_days": settings["recharge_warning_days"],
        "service_life": service,
    }
