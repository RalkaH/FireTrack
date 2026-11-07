# routers/employees.py (v1.3)
"""
Модуль для управления сотрудниками.
Позволяет добавлять, исправлять и удалять сотрудников и получать их список.
Сотрудника, который проводил проверки, удалить нельзя: журнал должен оставаться полным.
"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

import audit
from auth import EDITOR_ROLES, ROLE_ADMIN, get_current_active_user, require_role
from db import get_db
from models import Employee, Inspection, User
from schemas import EmployeeCreate, EmployeeRead, EmployeeUpdate

router = APIRouter(
    prefix="/employees",
    tags=["Employees"],
    dependencies=[Depends(get_current_active_user)],
)


@router.get("/", response_model=List[EmployeeRead])
def list_employees(db: Session = Depends(get_db)):
    """
    Получить полный список всех сотрудников.

    Args:
        db (Session): Сессия базы данных.

    Returns:
        List[Employee]: Список объектов сотрудников.
    """
    return db.query(Employee).order_by(Employee.full_name).all()


@router.post(
    "/",
    response_model=EmployeeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_employee(
    data: EmployeeCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(EDITOR_ROLES)),
):
    """
    Создать новую карточку сотрудника.

    Args:
        data (EmployeeCreate): Данные нового сотрудника (ФИО и должность).
        db (Session): Сессия базы данных.

    Returns:
        Employee: Созданный объект сотрудника с присвоенным ID и датой создания.
    """
    emp = Employee(
        full_name=data.full_name.strip(),
        position=data.position.strip(),
        created_at=datetime.now(timezone.utc),
    )
    db.add(emp)
    db.flush()
    audit.log(db, request, current_user, audit.ACTION_CREATE,
              f"Добавлен сотрудник «{emp.full_name}»",
              entity_type="employee", entity_id=emp.id,
              changes=audit.diff({}, audit.snapshot(emp, ("full_name", "position"))))
    db.commit()
    db.refresh(emp)
    return emp


def _get_or_404(db: Session, employee_id: int) -> Employee:
    """Возвращает сотрудника или 404."""
    emp = db.get(Employee, employee_id)
    if emp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    return emp


@router.put("/{employee_id}", response_model=EmployeeRead)
def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(EDITOR_ROLES)),
):
    """
    Исправить ФИО или должность сотрудника.

    Args:
        employee_id (int): ID сотрудника.
        data (EmployeeUpdate): Новые значения.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Инженер или администратор.

    Returns:
        Employee: Обновленный сотрудник.

    Raises:
        HTTPException: Если сотрудник не найден (404) или поле пустое (400).
    """
    emp = _get_or_404(db, employee_id)
    before = audit.snapshot(emp, ("full_name", "position"))
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        value = value.strip()
        if not value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Поле не может быть пустым")
        setattr(emp, field, value)
    changes = audit.diff(before, audit.snapshot(emp, ("full_name", "position")))
    if changes:
        audit.log(db, request, current_user, audit.ACTION_UPDATE, f"Изменен сотрудник «{emp.full_name}»",
                  entity_type="employee", entity_id=emp.id, changes=changes)
    db.commit()
    db.refresh(emp)
    return emp


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(
    employee_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([ROLE_ADMIN])),
):
    """
    Удалить сотрудника, который не проводил проверок (только администратор).

    Args:
        employee_id (int): ID сотрудника.
        request (Request): Запрос (для журнала).
        db (Session): Сессия базы данных.
        current_user (User): Администратор.

    Returns:
        None

    Raises:
        HTTPException: Если у сотрудника есть проверки в журнале (409).
    """
    emp = _get_or_404(db, employee_id)
    used = db.query(Inspection).filter(Inspection.employee_id == employee_id).count()
    if used:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Нельзя удалить: за сотрудником в журнале проверок: {used}")
    audit.log(db, request, current_user, audit.ACTION_DELETE, f"Удален сотрудник «{emp.full_name}»",
              entity_type="employee", entity_id=emp.id,
              changes={"full_name": {"old": emp.full_name, "new": None},
                       "position": {"old": emp.position, "new": None}})
    db.delete(emp)
    db.commit()
