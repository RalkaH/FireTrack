# status_logic.py (v1.0)
"""
Бизнес-логика статусов огнетушителей.

Здесь собраны правила, по которым определяется технический статус
огнетушителя, и общие запросы, которые используют разные роутеры
(последняя проверка каждого огнетушителя, массовый пересчет статусов).

Правила расчета статуса:

1. Статусы «Списан» и «На техническом обслуживании» выставляются вручную
   и при массовом пересчете не меняются.
2. Если проверок не было, огнетушитель считается просроченным.
3. Если при последней проверке обнаружены дефекты, ставится
   «Требует обслуживания».
4. Если дата следующей проверки уже прошла, ставится «Просрочено».
5. Иначе ставится «Актуально».
"""
from datetime import date, datetime, timezone
from typing import Dict, Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import FireExtinguisher, Inspection, Status

# Названия системных статусов
STATUS_ACTUAL = "Актуально"
STATUS_EXPIRED = "Просрочено"
STATUS_NEEDS_SERVICE = "Требует обслуживания"
STATUS_IN_SERVICE = "На техническом обслуживании"
STATUS_DECOMMISSIONED = "Списан"

DEFAULT_STATUSES = [
    {"name": STATUS_ACTUAL,
     "description": "Огнетушитель прошел проверку, срок не истек"},
    {"name": STATUS_EXPIRED,
     "description": "Необходима проверка, срок истек"},
    {"name": STATUS_NEEDS_SERVICE,
     "description": "Обнаружены дефекты при проверке"},
    {"name": STATUS_IN_SERVICE,
     "description": "Огнетушитель на ТО"},
    {"name": STATUS_DECOMMISSIONED,
     "description": "Огнетушитель выведен из эксплуатации"},
]

# Статусы, которые выставляются вручную и не трогаются автоматикой
MANUAL_STATUSES = {STATUS_DECOMMISSIONED, STATUS_IN_SERVICE}

# Значения полей осмотра, означающие дефект
DEFECT_VALUES = {"Неисправен", "Повреждена", "Поврежден", "Отсутствует"}


def ensure_default_statuses(db: Session) -> list:
    """
    Создает системные статусы, если их еще нет в базе.

    Args:
        db (Session): Сессия базы данных.

    Returns:
        list: Названия созданных статусов.
    """
    created = []
    for item in DEFAULT_STATUSES:
        exists = db.query(Status).filter(Status.name == item["name"]).first()
        if exists is None:
            db.add(Status(
                name=item["name"],
                description=item["description"],
                created_at=datetime.now(timezone.utc),
            ))
            created.append(item["name"])
    db.commit()
    return created


def status_ids_by_name(db: Session) -> Dict[str, int]:
    """
    Возвращает словарь «название статуса -> id».

    Args:
        db (Session): Сессия базы данных.

    Returns:
        Dict[str, int]: Соответствие названий и идентификаторов.
    """
    return {st.name: st.id for st in db.query(Status).all()}


def latest_inspections_subquery(db: Session):
    """
    Подзапрос с одной (самой свежей) проверкой на каждый огнетушитель.

    Если в один день было несколько проверок, берется добавленная позже.
    Колонки: fire_extinguisher_id, inspection_id, inspection_date,
    next_inspection_date.

    Args:
        db (Session): Сессия базы данных.

    Returns:
        Subquery: Подзапрос SQLAlchemy.
    """
    ranked = (
        db.query(
            Inspection.fire_extinguisher_id.label("fire_extinguisher_id"),
            Inspection.id.label("inspection_id"),
            Inspection.inspection_date.label("inspection_date"),
            Inspection.next_inspection_date.label("next_inspection_date"),
            func.row_number().over(
                partition_by=Inspection.fire_extinguisher_id,
                order_by=(Inspection.inspection_date.desc(), Inspection.id.desc()),
            ).label("rn"),
        )
        .subquery()
    )
    return (
        db.query(ranked)
        .filter(ranked.c.rn == 1)
        .subquery()
    )


def get_latest_inspection(db: Session, extinguisher_id: int) -> Optional[Inspection]:
    """
    Возвращает последнюю проверку огнетушителя.

    Args:
        db (Session): Сессия базы данных.
        extinguisher_id (int): ID огнетушителя.

    Returns:
        Optional[Inspection]: Последняя проверка или None.
    """
    return (
        db.query(Inspection)
        .filter(Inspection.fire_extinguisher_id == extinguisher_id)
        .order_by(Inspection.inspection_date.desc(), Inspection.id.desc())
        .first()
    )


def has_defects(inspection: Inspection) -> bool:
    """
    Проверяет, были ли обнаружены дефекты при проверке.

    Args:
        inspection (Inspection): Запись о проверке.

    Returns:
        bool: True, если хотя бы одно поле осмотра указывает на дефект.
    """
    values = (
        inspection.visual_inspection,
        inspection.seal_condition,
        inspection.safety_pin_condition,
        inspection.hose_condition,
    )
    return any((v or "").strip() in DEFECT_VALUES for v in values)


def compute_status_name(last_inspection: Optional[Inspection], today: Optional[date] = None) -> str:
    """
    Определяет статус огнетушителя по его последней проверке.

    Args:
        last_inspection (Optional[Inspection]): Последняя проверка или None.
        today (Optional[date]): Текущая дата (для тестов).

    Returns:
        str: Название статуса.
    """
    today = today or date.today()
    if last_inspection is None:
        return STATUS_EXPIRED
    if has_defects(last_inspection):
        return STATUS_NEEDS_SERVICE
    if last_inspection.next_inspection_date < today:
        return STATUS_EXPIRED
    return STATUS_ACTUAL


def recalculate_statuses(
    db: Session,
    extinguisher_ids: Optional[Iterable[int]] = None,
    keep_manual: Iterable[str] = tuple(MANUAL_STATUSES),
) -> int:
    """
    Пересчитывает статусы огнетушителей и сохраняет изменения.

    Args:
        db (Session): Сессия базы данных.
        extinguisher_ids (Optional[Iterable[int]]): Ограничить пересчет этими ID.
            Если не указано, пересчитывается весь парк.
        keep_manual (Iterable[str]): Статусы, которые нельзя менять.

    Returns:
        int: Количество огнетушителей, у которых изменился статус.
    """
    ids = status_ids_by_name(db)
    required = (STATUS_ACTUAL, STATUS_EXPIRED, STATUS_NEEDS_SERVICE)
    if any(name not in ids for name in required):
        ensure_default_statuses(db)
        ids = status_ids_by_name(db)

    protected_ids = {ids[name] for name in keep_manual if name in ids}

    query = db.query(FireExtinguisher)
    if extinguisher_ids is not None:
        id_list = list(extinguisher_ids)
        if not id_list:
            return 0
        query = query.filter(FireExtinguisher.id.in_(id_list))

    today = date.today()
    changed = 0
    for fe in query.all():
        if fe.status_id in protected_ids:
            continue
        new_status_id = ids[compute_status_name(get_latest_inspection(db, fe.id), today)]
        if fe.status_id != new_status_id:
            fe.status_id = new_status_id
            fe.updated_at = datetime.now(timezone.utc)
            changed += 1

    db.commit()
    return changed
