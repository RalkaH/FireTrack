# service_logic.py (v1.0)
"""
История технического обслуживания огнетушителей.

Каждое испытание, перезарядка и ремонт хранятся отдельной записью
(таблица ``ServiceRecords``, графы формы А.2 ГОСТ Р 59641-2021). Даты
последней перезарядки и последнего испытания в карточке огнетушителя
вычисляются по этой истории, поэтому исправление или удаление записи
автоматически исправляет и сроки.
"""
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from deadlines import add_months, recharge_interval
from models import FireExtinguisher, ServiceRecord


def default_next_dates(fe: FireExtinguisher, settings: Dict[str, Any], service_date: date,
                       tested: bool, recharged: bool) -> Dict[str, Optional[date]]:
    """
    Считает сроки следующего испытания и перезарядки после выполненных работ.

    Args:
        fe (FireExtinguisher): Огнетушитель.
        settings (Dict[str, Any]): Настройки приложения.
        service_date (date): Дата работ.
        tested (bool): Проведено испытание.
        recharged (bool): Проведена перезарядка.

    Returns:
        Dict[str, Optional[date]]: ``next_test_date`` и ``next_recharge_date``
        (None, если такие работы не проводились или интервал неизвестен).
    """
    next_test = None
    if tested and settings.get("test_interval_months"):
        next_test = add_months(service_date, int(settings["test_interval_months"]))
    next_recharge = None
    interval = recharge_interval(fe, settings) if recharged else None
    if interval:
        next_recharge = add_months(service_date, interval)
    return {"next_test_date": next_test, "next_recharge_date": next_recharge}


def sync_extinguisher_dates(db: Session, fe: FireExtinguisher) -> None:
    """
    Обновляет в карточке даты последней перезарядки и испытания по истории (без commit).

    Args:
        db (Session): Сессия базы данных.
        fe (FireExtinguisher): Огнетушитель.
    """
    db.flush()
    fe.last_recharge_date = (
        db.query(func.max(ServiceRecord.service_date))
        .filter(ServiceRecord.fire_extinguisher_id == fe.id, ServiceRecord.recharged.is_(True))
        .scalar()
    )
    fe.last_test_date = (
        db.query(func.max(ServiceRecord.service_date))
        .filter(ServiceRecord.fire_extinguisher_id == fe.id, ServiceRecord.tested.is_(True))
        .scalar()
    )
    fe.updated_at = datetime.now(timezone.utc)


def initial_recharge_record(fe: FireExtinguisher, settings: Dict[str, Any], recharge_date: date,
                            username: Optional[str]) -> ServiceRecord:
    """
    Запись о перезарядке, известной на момент постановки огнетушителя на учет.

    Args:
        fe (FireExtinguisher): Огнетушитель (может быть еще не сохранен).
        settings (Dict[str, Any]): Настройки приложения.
        recharge_date (date): Дата последней перезарядки из карточки или файла.
        username (Optional[str]): Кто добавил.

    Returns:
        ServiceRecord: Запись, привязанная к огнетушителю.
    """
    next_dates = default_next_dates(fe, settings, recharge_date, False, True)
    return ServiceRecord(
        fire_extinguisher=fe,
        service_date=recharge_date,
        recharged=True,
        tested=False,
        repaired=False,
        next_recharge_date=next_dates["next_recharge_date"],
        comments="Указано при постановке на учет",
        created_at=datetime.now(timezone.utc),
        created_by=username,
    )
