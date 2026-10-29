# routers/locations.py (v1.1)
"""
Модуль управления местами расположения (локациями).
Предоставляет возможности добавления новых кабинетов/этажей и получения их списка.
"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import EDITOR_ROLES, get_current_active_user, require_role
from db import get_db
from models import Location, User
from schemas import LocationCreate, LocationRead

router = APIRouter(
    prefix="/locations",
    tags=["Locations"],
    dependencies=[Depends(get_current_active_user)],
)


@router.get("/", response_model=List[LocationRead])
def list_locations(db: Session = Depends(get_db)):
    """
    Получить список всех зарегистрированных локаций.

    Args:
        db (Session): Сессия базы данных.

    Returns:
        List[Location]: Список всех мест.
    """
    return db.query(Location).order_by(Location.name).all()


@router.post(
    "/",
    response_model=LocationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_location(
    data: LocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(EDITOR_ROLES)),
):
    """
    Зарегистрировать новое место установки огнетушителей.

    Args:
        data (LocationCreate): Данные о месте (название, описание).
        db (Session): Сессия базы данных.

    Returns:
        Location: Созданный объект места.

    Raises:
        HTTPException: Если локация с таким именем уже существует (400).
    """
    existing = (
        db.query(Location)
        .filter(Location.name == data.name.strip())
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Место с таким названием уже существует",
        )

    loc = Location(
        name=data.name.strip(),
        description=data.description,
        created_at=datetime.now(timezone.utc),
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc
