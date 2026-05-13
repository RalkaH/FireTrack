# routers/employees.py
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
    return db.query(Employee).all()


@router.post(
    "/",
    response_model=EmployeeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_employee(data: EmployeeCreate, db: Session = Depends(get_db)):
    emp = Employee(
        full_name=data.full_name,
        position=data.position,
        created_at=datetime.utcnow(),
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp