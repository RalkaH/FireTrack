# report_data.py (v1.1)
"""
Данные для отчетов.

Каждая функция возвращает готовые строки (словари), из которых потом
строятся XLSX-файл (``xlsx_export``) и страница для печати
(``static/print.html``). Так оба формата всегда показывают одно и то же.

Отчеты:

1. :func:`journal_rows` — журнал проверок за период.
2. :func:`maintenance_rows` — записи о техническом обслуживании и ремонте для
   Журнала эксплуатации систем противопожарной защиты по форме А.2
   приложения А ГОСТ Р 59641-2021.
3. :func:`card_rows` — карточки учета огнетушителей по форме А.1.
4. :func:`fleet_summary` — состояние парка: сводка по статусам и местам,
   проблемные огнетушители, ближайшие проверки, перезарядки, испытания
   и сроки службы.

Аннулированные проверки в отчеты не попадают.
"""
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app_settings import get_settings
from deadlines import STATE_OVERDUE, STATE_SOON, compute_deadlines
from models import Employee, FireExtinguisher, Inspection, Location, ServiceRecord, Status
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
        .filter(Inspection.annulled_at.is_(None))
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


def _inspection_result(insp: Inspection) -> str:
    """Результаты осмотра одной строкой для графы журнала."""
    parts = []
    for label, value in (("внешний осмотр", insp.visual_inspection), ("пломба", insp.seal_condition),
                         ("чека", insp.safety_pin_condition), ("шланг", insp.hose_condition)):
        if value:
            parts.append(f"{label}: {value.strip().lower()}")
    if insp.pressure is not None:
        parts.append(f"давление {insp.pressure:g} МПа")
    if insp.weight is not None:
        parts.append(f"масса {insp.weight:g} кг")
    if insp.comments:
        parts.append(insp.comments.strip())
    return "; ".join(parts) or "Замечаний нет"


def _work_text(record: ServiceRecord) -> str:
    """Дата, виды работ и организация для графы журнала."""
    works = [name for flag, name in ((record.tested, "испытание"), (record.recharged, "перезарядка"),
                                     (record.repaired, "ремонт")) if flag]
    text = f"{record.service_date:%d.%m.%Y}, {', '.join(works)}"
    return f"{text}; {record.organization}" if record.organization else text


def maintenance_rows(db: Session, date_from: Optional[date], date_to: Optional[date]) -> List[Dict[str, Any]]:
    """
    Записи журнала по форме А.2 приложения А ГОСТ Р 59641-2021.

    Графы формы: номер и марка огнетушителя; дата проведения испытания,
    перезарядки, ремонта и организация; результаты осмотра и испытания на
    прочность; срок следующего планового испытания; дата проведения
    перезарядки; марка (концентрация) заряженного ОТВ; результат осмотра
    после перезарядки; дата следующей плановой перезарядки; должность,
    фамилия, инициалы и подпись ответственного лица.

    По п. 5.1.1 стандарта ТО включает проверку, испытания и перезарядку,
    поэтому в журнал попадают и проверки, и записи об испытаниях,
    перезарядке и ремонте. Подпись ставится от руки.

    Args:
        db (Session): Сессия базы данных.
        date_from (Optional[date]): Начало периода.
        date_to (Optional[date]): Конец периода.

    Returns:
        List[Dict[str, Any]]: Строки журнала в порядке дат.
    """
    rows: List[Dict[str, Any]] = []
    for insp, fe, _loc, emp in _journal_query(db, date_from, date_to).all():
        rows.append({
            "date": insp.inspection_date,
            "extinguisher": f"{fe.inventory_number}, {fe.type}",
            "work": f"{insp.inspection_date:%d.%m.%Y}, проверка",
            "test_result": _inspection_result(insp),
            "next_test_date": None,
            "recharge_date": None,
            "agent_brand": "",
            "post_recharge_result": "",
            "next_recharge_date": None,
            "responsible": f"{emp.position}, {emp.full_name}",
        })

    query = (
        db.query(ServiceRecord, FireExtinguisher)
        .join(FireExtinguisher, ServiceRecord.fire_extinguisher_id == FireExtinguisher.id)
    )
    if date_from is not None:
        query = query.filter(ServiceRecord.service_date >= date_from)
    if date_to is not None:
        query = query.filter(ServiceRecord.service_date <= date_to)
    for record, fe in query.all():
        rows.append({
            "date": record.service_date,
            "extinguisher": f"{fe.inventory_number}, {fe.type}",
            "work": _work_text(record),
            "test_result": record.test_result or "",
            "next_test_date": record.next_test_date,
            "recharge_date": record.service_date if record.recharged else None,
            "agent_brand": record.agent_brand or "",
            "post_recharge_result": record.post_recharge_result or "",
            "next_recharge_date": record.next_recharge_date,
            "responsible": record.responsible or "",
        })

    rows.sort(key=lambda r: (r["date"], r["extinguisher"]))
    for n, row in enumerate(rows, start=1):
        row["n"] = n
    return rows


def card_rows(db: Session, extinguisher_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Карточки учета огнетушителей по форме А.1 приложения А ГОСТ Р 59641-2021.

    Args:
        db (Session): Сессия базы данных.
        extinguisher_id (Optional[int]): Один огнетушитель. Если не указан,
            карточки всех огнетушителей, кроме списанных.

    Returns:
        List[Dict[str, Any]]: Поля формы для каждого огнетушителя.
    """
    settings = get_settings(db)
    query = (
        db.query(FireExtinguisher, Location, Status)
        .join(Location, FireExtinguisher.location_id == Location.id)
        .join(Status, FireExtinguisher.status_id == Status.id)
    )
    if extinguisher_id is not None:
        query = query.filter(FireExtinguisher.id == extinguisher_id)
    else:
        query = query.filter(Status.name != STATUS_DECOMMISSIONED)

    cards = []
    for fe, loc, _st in query.order_by(FireExtinguisher.inventory_number).all():
        d = compute_deadlines(fe, settings)
        cards.append({
            "number": fe.inventory_number,
            "placed_date": fe.commissioning_date,
            "location": loc.name,
            "type": fe.type,
            "manufacturer": fe.manufacturer or "",
            "serial_number": fe.serial_number or "",
            "manufacture_date": fe.manufacture_date,
            "next_recharge_date": d["next_recharge_date"],
            "service_life_years": d["service_life_years"],
            "service_end_date": d["service_end_date"],
        })
    return cards


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
        и скоро), ``service_life`` (истек и скоро истекает), ``tests``
        (испытания просрочены или скоро).
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
    problems, upcoming, recharge, service, tests = [], [], [], [], []
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
        if d["test_state"] in (STATE_OVERDUE, STATE_SOON):
            tests.append({**base, "next_test": d["next_test_date"],
                          "days_left": (d["next_test_date"] - today).days, "state": d["test_state"]})

    upcoming.sort(key=lambda r: r["next_inspection"])
    recharge.sort(key=lambda r: r["next_recharge"])
    service.sort(key=lambda r: r["service_end"])
    tests.sort(key=lambda r: r["next_test"])
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
        "tests": tests,
    }
