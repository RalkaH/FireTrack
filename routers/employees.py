# routers/employees.py (v1.1)
"""
Модуль для управления сотрудниками.
Содержит маршруты для получения списка сотрудников и добавления новых.
"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from auth import EDITOR_ROLES, get_current_active_user, require_role
from db import get_db
from models import Employee, User
from schemas import EmployeeCreate, EmployeeRead

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
    db.commit()
    db.refresh(emp)
    return emp
