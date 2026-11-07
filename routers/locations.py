# routers/locations.py (v1.3)
"""
Модуль управления местами расположения (локациями).
Позволяет добавлять, исправлять и удалять места и получать их список.
Место, в котором есть огнетушители, удалить нельзя.
"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

import audit
from auth import EDITOR_ROLES, ROLE_ADMIN, get_current_active_user, require_role
from db import get_db
from models import FireExtinguisher, Location, User
from schemas import LocationCreate, LocationRead, LocationUpdate

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
    request: Request,
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
    db.flush()
    audit.log(db, request, current_user, audit.ACTION_CREATE, f"Добавлено место «{loc.name}»",
              entity_type="location", entity_id=loc.id,
              changes=audit.diff({}, audit.snapshot(loc, ("name", "description"))))
    db.commit()
    db.refresh(loc)
    return loc


def _get_or_404(db: Session, location_id: int) -> Location:
    """Возвращает место или 404."""
    loc = db.get(Location, location_id)
    if loc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Место не найдено")
    return loc


@router.put("/{location_id}", response_model=LocationRead)
def update_location(
    location_id: int,
    data: LocationUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(EDITOR_ROLES)),
):
    """
    Исправить название или описание места.

    Args:
        location_id (int): ID места.
        data (LocationUpdate): Новые значения.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Инженер или администратор.

    Returns:
        Location: Обновленное место.

    Raises:
        HTTPException: Если место не найдено (404) или название занято (400).
    """
    loc = _get_or_404(db, location_id)
    before = audit.snapshot(loc, ("name", "description"))
    update = data.model_dump(exclude_unset=True)
    if update.get("name") is not None:
        name = update["name"].strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите название места")
        duplicate = db.query(Location).filter(Location.name == name, Location.id != location_id).first()
        if duplicate:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Место с таким названием уже существует")
        loc.name = name
    if "description" in update:
        loc.description = (update["description"] or "").strip() or None
    changes = audit.diff(before, audit.snapshot(loc, ("name", "description")))
    if changes:
        audit.log(db, request, current_user, audit.ACTION_UPDATE, f"Изменено место «{loc.name}»",
                  entity_type="location", entity_id=loc.id, changes=changes)
    db.commit()
    db.refresh(loc)
    return loc


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_location(
    location_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ROLE_ADMIN])),
):
    """
    Удалить место, в котором нет огнетушителей (только администратор).

    Args:
        location_id (int): ID места.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Администратор.

    Returns:
        None

    Raises:
        HTTPException: Если в этом месте есть огнетушители (409).
    """
    loc = _get_or_404(db, location_id)
    used = db.query(FireExtinguisher).filter(FireExtinguisher.location_id == location_id).count()
    if used:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Нельзя удалить: в этом месте огнетушителей: {used}. Сначала перенесите их")
    audit.log(db, request, current_user, audit.ACTION_DELETE, f"Удалено место «{loc.name}»",
              entity_type="location", entity_id=loc.id,
              changes={"name": {"old": loc.name, "new": None},
                       "description": {"old": loc.description, "new": None}})
    db.delete(loc)
    db.commit()
