# routers/employees.py (v1.1)
"""
Модуль для управления сотрудниками.
Содержит маршруты для получения списка сотрудников и добавления новых.
"""
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db import get_db
from models import Employee
from schemas import EmployeeCreate, EmployeeRead

router = APIRouter(
    prefix="/employees",
    tags=["Employees"],
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
    return db.query(Employee).all()


@router.post(
    "/",
    response_model=EmployeeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_employee(data: EmployeeCreate, db: Session = Depends(get_db)):
    """
    Создать новую карточку сотрудника.

    Args:
        data (EmployeeCreate): Данные нового сотрудника (ФИО и должность).
        db (Session): Сессия базы данных.

    Returns:
        Employee: Созданный объект сотрудника с присвоенным ID и датой создания.
    """
    emp = Employee(
        full_name=data.full_name,
        position=data.position,
        created_at=datetime.utcnow(),
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp
