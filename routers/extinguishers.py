# routers/extinguishers.py (v1.1)
"""
Модуль для управления огнетушителями (CRUD операции).
Включает фильтрацию, поиск по инвентарному номеру, создание, обновление и удаление оборудования.
"""
from datetime import datetime, timezone, date as date_type
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from auth import get_current_active_user, require_role
from db import get_db
from models import User, FireExtinguisher, Location, Status, Inspection
from schemas import (
    FireExtinguisherCreate,
    FireExtinguisherRead,
    FireExtinguisherUpdate,
)

# ВАЖНО: router В САМОМ НАЧАЛЕ
router = APIRouter(
    prefix="/extinguishers",
    tags=["Fire Extinguishers"],
)


@router.get("/", response_model=List[FireExtinguisherRead])
def list_extinguishers(
    location_id: Optional[int] = Query(None, description="Фильтр по ID места"),
    status_id: Optional[int] = Query(None, description="Фильтр по ID статуса"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Получить список всех огнетушителей с возможностью фильтрации.

    Args:
        location_id (Optional[int]): ID местоположения для фильтрации.
        status_id (Optional[int]): ID статуса для фильтрации.
        db (Session): Сессия базы данных.
        current_user (User): Авторизованный пользователь.

    Returns:
        List[FireExtinguisher]: Отфильтрованный список оборудования.
    """
    query = db.query(FireExtinguisher)

    if location_id is not None:
        query = query.filter(FireExtinguisher.location_id == location_id)

    if status_id is not None:
        query = query.filter(FireExtinguisher.status_id == status_id)

    return query.all()


@router.get("/search/inventory", response_model=List[FireExtinguisherRead])
def search_by_inventory(
    query: str = Query(..., min_length=1,
                       description="Поисковый запрос по инвентарному номеру"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Поиск огнетушителей по инвентарному номеру (частичное совпадение).

    Args:
        query (str): Подстрока инвентарного номера для поиска.
        db (Session): Сессия базы данных.
        current_user (User): Авторизованный пользователь.

    Returns:
        List[FireExtinguisher]: Список найденного оборудования.
    """
    results = (
        db.query(FireExtinguisher)
        .filter(FireExtinguisher.inventory_number.contains(query))
        .all()
    )

    return results


@router.get("/{extinguisher_id}", response_model=FireExtinguisherRead)
def get_extinguisher(
    extinguisher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Получить детальную информацию об огнетушителе по его ID.

    Args:
        extinguisher_id (int): Уникальный идентификатор огнетушителя.
        db (Session): Сессия базы данных.
        current_user (User): Авторизованный пользователь.

    Returns:
        FireExtinguisher: Объект огнетушителя.

    Raises:
        HTTPException: Если огнетушитель с указанным ID не найден (404).
    """
    extinguisher = db.query(FireExtinguisher).get(extinguisher_id)

    if extinguisher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Огнетушитель не найден",
        )

    return extinguisher


@router.post("/", response_model=FireExtinguisherRead, status_code=status.HTTP_201_CREATED)
def create_extinguisher(
    data: FireExtinguisherCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """
    Добавить новый огнетушитель в систему. Доступно только администраторам и инженерам.

    Args:
        data (FireExtinguisherCreate): Данные для создания.
        db (Session): Сессия базы данных.
        current_user (User): Авторизованный пользователь с соответствующей ролью.

    Returns:
        FireExtinguisher: Созданный объект огнетушителя.

    Raises:
        HTTPException: В случае дубликата инвентарного номера, некорректных дат или отсутствия связанных объектов (локации/статуса).
    """
    # Проверка уникальности инвентарного номера
    existing = (
        db.query(FireExtinguisher)
        .filter(FireExtinguisher.inventory_number == data.inventory_number)
        .first()
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Огнетушитель с инвентарным номером '{data.inventory_number}' уже существует",
        )

    # Валидация дат (не из будущего)
    today = date_type.today()

    if data.manufacture_date and data.manufacture_date > today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дата изготовления не может быть из будущего",
        )

    if data.commissioning_date and data.commissioning_date > today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дата ввода в эксплуатацию не может быть из будущего",
        )

    # Проверка существования связанных объектов
    location = db.query(Location).get(data.location_id)
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Место расположения не найдено",
        )

    status_obj = db.query(Status).get(data.status_id)
    if status_obj is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Статус не найден",
        )

    # Создание огнетушителя
    now = datetime.now(timezone.utc)

    extinguisher = FireExtinguisher(
        inventory_number=data.inventory_number,
        type=data.type,
        capacity=data.capacity,
        manufacturer=data.manufacturer,
        manufacture_date=data.manufacture_date,
        commissioning_date=data.commissioning_date,
        location_id=data.location_id,
        status_id=data.status_id,
        created_at=now,
        updated_at=now,
    )

    db.add(extinguisher)
    db.commit()
    db.refresh(extinguisher)

    return extinguisher


@router.put("/{extinguisher_id}", response_model=FireExtinguisherRead)
def update_extinguisher(
    extinguisher_id: int,
    data: FireExtinguisherUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """
    Обновить данные существующего огнетушителя. Доступно только администраторам и инженерам.

    Args:
        extinguisher_id (int): Идентификатор обновляемого огнетушителя.
        data (FireExtinguisherUpdate): Новые данные.
        db (Session): Сессия базы данных.
        current_user (User): Авторизованный пользователь.

    Returns:
        FireExtinguisher: Обновленный объект.

    Raises:
        HTTPException: Если объект не найден, дублируется номер или указаны неверные связанные ключи.
    """
    extinguisher = db.query(FireExtinguisher).get(extinguisher_id)

    if extinguisher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Огнетушитель не найден",
        )

    # Проверка уникальности инвентарного номера при изменении
    if data.inventory_number is not None:
        existing = (
            db.query(FireExtinguisher)
            .filter(
                FireExtinguisher.inventory_number == data.inventory_number,
                FireExtinguisher.id != extinguisher_id,
            )
            .first()
        )

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Огнетушитель с инвентарным номером '{data.inventory_number}' уже существует",
            )

    # Валидация дат
    today = date_type.today()

    if data.manufacture_date and data.manufacture_date > today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дата изготовления не может быть из будущего",
        )

    if data.commissioning_date and data.commissioning_date > today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дата ввода в эксплуатацию не может быть из будущего",
        )

    # Проверка существования связанных объектов
    if data.location_id is not None:
        location = db.query(Location).get(data.location_id)
        if location is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Место расположения не найдено",
            )

    if data.status_id is not None:
        status_obj = db.query(Status).get(data.status_id)
        if status_obj is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Статус не найден",
            )

    # Обновление полей
    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(extinguisher, field, value)

    extinguisher.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(extinguisher)

    return extinguisher


@router.delete("/{extinguisher_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_extinguisher(
    extinguisher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """
    Полностью удалить огнетушитель и всю историю его проверок (каскадное удаление).
    Доступно ИСКЛЮЧИТЕЛЬНО администраторам.

    Args:
        extinguisher_id (int): Идентификатор удаляемого оборудования.
        db (Session): Сессия базы данных.
        current_user (User): Текущий администратор.

    Returns:
        None

    Raises:
        HTTPException: Если огнетушитель не найден.
    """
    extinguisher = db.query(FireExtinguisher).get(extinguisher_id)

    if extinguisher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Огнетушитель не найден",
        )

    # Каскадное удаление проверок
    db.query(Inspection).filter(
        Inspection.fire_extinguisher_id == extinguisher_id
    ).delete()

    # Удаление огнетушителя
    db.delete(extinguisher)
    db.commit()

    return None
