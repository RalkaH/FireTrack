from datetime import date, datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db import get_db
from models import Status, FireExtinguisher, Inspection
from schemas import StatusCreate, StatusRead


router = APIRouter(
    prefix="/statuses",
    tags=["Statuses"],
)


@router.get("/", response_model=List[StatusRead])
def list_statuses(db: Session = Depends(get_db)):
    return db.query(Status).all()


@router.post(
    "/",
    response_model=StatusRead,
    status_code=status.HTTP_201_CREATED,
)
def create_status(data: StatusCreate, db: Session = Depends(get_db)):
    existing = db.query(Status).filter(Status.name == data.name).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Статус с таким названием уже существует",
        )

    status_obj = Status(
        name=data.name,
        description=data.description,
        created_at=datetime.now(timezone.utc),
    )

    db.add(status_obj)
    db.commit()
    db.refresh(status_obj)

    return status_obj


@router.post("/init-defaults", status_code=status.HTTP_201_CREATED)
def init_default_statuses(db: Session = Depends(get_db)):
    """
    Создать стандартные статусы для системы, если их еще нет.
    """
    default_statuses = [
        {"name": "Актуально", "description": "Огнетушитель прошел проверку, срок не истек"},
        {"name": "Просрочено", "description": "Необходима проверка, срок истек"},
        {"name": "Требует обслуживания", "description": "Обнаружены дефекты при проверке"},
        {"name": "На техническом обслуживании", "description": "Огнетушитель на ТО"},
        {"name": "Списан", "description": "Огнетушитель выведен из эксплуатации"},
    ]

    created: list[str] = []
    for status_data in default_statuses:
        existing = (
            db.query(Status)
            .filter(Status.name == status_data["name"])
            .first()
        )
        if existing is None:
            status_obj = Status(
                name=status_data["name"],
                description=status_data["description"],
                created_at=datetime.now(timezone.utc),
            )
            db.add(status_obj)
            created.append(status_data["name"])

    db.commit()

    return {
        "detail": "Инициализация завершена",
        "created": created,
    }


@router.post("/recalculate")
def recalculate_statuses(db: Session = Depends(get_db)):
    """
    Пересчитать статусы огнетушителей по дате следующей проверки.
    Если next_inspection_date < сегодня -> статус 'Просрочено',
    иначе -> 'Актуально'.
    """
    status_actual = db.query(Status).filter(Status.name == "Актуально").first()
    status_expired = db.query(Status).filter(Status.name == "Просрочено").first()

    if status_actual is None or status_expired is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не найдены статусы 'Актуально' и 'Просрочено'",
        )

    today = date.today()
    extinguishers = db.query(FireExtinguisher).all()

    for fe in extinguishers:
        # Берём последнюю запись проверки для этого огнетушителя
        last_insp = (
            db.query(Inspection)
            .filter(Inspection.fire_extinguisher_id == fe.id)
            .order_by(Inspection.inspection_date.desc())
            .first()
        )

        if last_insp is None:
            # Без проверок считаем просроченным
            fe.status_id = status_expired.id
            continue

        # Явно берём дату следующей проверки (для Pylance)
        next_date: date = last_insp.next_inspection_date  # type: ignore[assignment]

        if next_date < today:
            fe.status_id = status_expired.id
        else:
            fe.status_id = status_actual.id

    db.commit()

    return {"detail": "Статусы пересчитаны"}
