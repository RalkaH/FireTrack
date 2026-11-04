# routers/users.py (v1.0)
"""
Управление пользователями (только для администратора).

Возможности: список, создание, изменение ФИО, email и роли, блокировка
и разблокировка, сброс пароля. Защита от выстрела себе в ногу:

1. Нельзя заблокировать себя и понизить собственную роль.
2. Нельзя оставить систему без единого активного администратора.

Блокировка, смена роли и сброс пароля отзывают все токены пользователя,
поэтому изменения действуют сразу, а не после истечения сессии.
Удаления пользователей нет намеренно: для истории и журнала действий
учетную запись лучше заблокировать.
"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

import audit
from auth import ROLE_ADMIN, get_current_active_user, get_password_hash, require_role, revoke_tokens
from db import get_db
from models import User
from schemas import (
    PasswordReset,
    UserCreate,
    UserRead,
    UserStatusUpdate,
    UserUpdate,
    validate_password_strength,
)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    dependencies=[Depends(get_current_active_user)],
)

_admin_only = require_role([ROLE_ADMIN])
_AUDIT_FIELDS = ("username", "full_name", "email", "role", "is_active", "must_change_password")


def _get_user(db: Session, user_id: int) -> User:
    """Возвращает пользователя или 404."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    return user


def _active_admins_except(db: Session, user_id: int) -> int:
    """Количество активных администраторов, не считая указанного пользователя."""
    return (
        db.query(User)
        .filter(User.role == ROLE_ADMIN, User.is_active == 1, User.id != user_id)
        .count()
    )


def _check_email_free(db: Session, email: str, user_id: int = 0) -> None:
    """Проверяет, что email не занят другим пользователем."""
    taken = (
        db.query(User)
        .filter(func.lower(User.email) == email.lower(), User.id != user_id)
        .first()
    )
    if taken is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Пользователь с таким email уже существует")


@router.get("/", response_model=List[UserRead])
def list_users(db: Session = Depends(get_db), _: User = Depends(_admin_only)):
    """
    Список всех пользователей.

    Args:
        db (Session): Сессия базы данных.

    Returns:
        List[User]: Пользователи, отсортированные по логину.
    """
    return db.query(User).order_by(User.username).all()


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin_only),
):
    """
    Создать пользователя.

    Args:
        data (UserCreate): Логин, ФИО, email, роль, пароль.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Администратор.

    Returns:
        User: Созданный пользователь.

    Raises:
        HTTPException: Если логин или email уже заняты (400).
    """
    if db.query(User).filter(func.lower(User.username) == data.username.lower()).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Логин '{data.username}' уже занят")
    _check_email_free(db, data.email)

    user = User(
        username=data.username,
        email=data.email,
        full_name=data.full_name,
        role=data.role,
        hashed_password=get_password_hash(data.password),
        is_active=1,
        must_change_password=data.must_change_password,
        token_version=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()
    audit.log(db, request, current_user, audit.ACTION_CREATE,
              f"Создан пользователь «{user.username}» с ролью {user.role}",
              entity_type="user", entity_id=user.id,
              changes=audit.diff({}, audit.snapshot(user, _AUDIT_FIELDS)))
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    data: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin_only),
):
    """
    Изменить ФИО, email или роль пользователя.

    Args:
        user_id (int): ID пользователя.
        data (UserUpdate): Новые значения (только переданные поля).
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Администратор.

    Returns:
        User: Обновленный пользователь.

    Raises:
        HTTPException: Попытка понизить себя или последнего администратора (400).
    """
    user = _get_user(db, user_id)
    before = audit.snapshot(user, _AUDIT_FIELDS)
    update = data.model_dump(exclude_unset=True, exclude_none=True)

    new_role = update.get("role")
    if new_role and new_role != user.role and user.role == ROLE_ADMIN:
        if user.id == current_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Нельзя понизить собственную роль")
        if bool(user.is_active) and _active_admins_except(db, user.id) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Нельзя оставить систему без активного администратора")
    if "email" in update:
        _check_email_free(db, update["email"], user.id)

    for field, value in update.items():
        setattr(user, field, value)
    if new_role and new_role != before["role"]:
        revoke_tokens(user)  # новые права действуют сразу

    changes = audit.diff(before, audit.snapshot(user, _AUDIT_FIELDS))
    if changes:
        audit.log(db, request, current_user, audit.ACTION_UPDATE,
                  f"Изменен пользователь «{user.username}»",
                  entity_type="user", entity_id=user.id, changes=changes)
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/status", response_model=UserRead)
def set_user_status(
    user_id: int,
    data: UserStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin_only),
):
    """
    Заблокировать или разблокировать пользователя.

    Заблокированный пользователь не может войти, а его текущие токены
    сразу перестают работать.

    Args:
        user_id (int): ID пользователя.
        data (UserStatusUpdate): ``is_active``: true разблокирует, false блокирует.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Администратор.

    Returns:
        User: Пользователь с новым статусом.

    Raises:
        HTTPException: Попытка заблокировать себя или последнего администратора (400).
    """
    user = _get_user(db, user_id)
    if bool(user.is_active) == data.is_active:
        return user

    if not data.is_active:
        if user.id == current_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Нельзя заблокировать самого себя")
        if user.role == ROLE_ADMIN and _active_admins_except(db, user.id) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Нельзя заблокировать последнего активного администратора")
        user.is_active = 0
        revoke_tokens(user)
        action, summary = audit.ACTION_BLOCK, f"Заблокирован пользователь «{user.username}»"
    else:
        user.is_active = 1
        action, summary = audit.ACTION_UNBLOCK, f"Разблокирован пользователь «{user.username}»"

    audit.log(db, request, current_user, action, summary, entity_type="user", entity_id=user.id,
              changes={"is_active": {"old": not data.is_active, "new": data.is_active}})
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", response_model=UserRead)
def reset_password(
    user_id: int,
    data: PasswordReset,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin_only),
):
    """
    Задать пользователю временный пароль.

    При следующем входе пользователь обязан сменить его на свой.
    Все текущие сессии пользователя завершаются.

    Args:
        user_id (int): ID пользователя.
        data (PasswordReset): Временный пароль.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Администратор.

    Returns:
        User: Пользователь.

    Raises:
        HTTPException: Если пароль слишком простой (422).
    """
    user = _get_user(db, user_id)
    try:
        validate_password_strength(data.new_password, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    user.hashed_password = get_password_hash(data.new_password)
    user.must_change_password = True
    revoke_tokens(user)
    audit.log(db, request, current_user, audit.ACTION_PASSWORD_RESET,
              f"Сброшен пароль пользователя «{user.username}»",
              entity_type="user", entity_id=user.id)
    db.commit()
    db.refresh(user)
    return user
