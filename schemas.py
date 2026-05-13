# schemas.py (v1.1)
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------- Health ----------

class HealthResponse(BaseModel):
    status: str


# ---------- Locations ----------

class LocationBase(BaseModel):
    name: str = Field(..., description="Название места (кабинет, этаж)")
    description: Optional[str] = Field(None, description="Описание места")


class LocationCreate(LocationBase):
    pass


class LocationRead(LocationBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Statuses ----------

class StatusBase(BaseModel):
    name: str = Field(..., description="Название статуса")
    description: str = Field(..., description="Описание статуса")


class StatusCreate(StatusBase):
    pass


class StatusRead(StatusBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- FireExtinguishers ----------

class FireExtinguisherBase(BaseModel):
    inventory_number: str = Field(..., description="Инвентарный номер")
    type: str = Field(..., description="Тип огнетушителя (ОУ-8 и т.п.)")
    capacity: float = Field(..., gt=0, description="Вместимость (л / кг)")
    manufacturer: Optional[str] = Field(None, description="Производитель")
    manufacture_date: Optional[date] = Field(
        None, description="Дата изготовления")
    commissioning_date: Optional[date] = Field(
        None, description="Дата ввода в эксплуатацию")
    location_id: int = Field(..., description="ID места (Locations.id)")
    status_id: int = Field(..., description="ID статуса (Statuses.id)")

    @field_validator('manufacture_date', 'commissioning_date')
    @classmethod
    def not_in_future(cls, v):
        if v and v > date.today():
            raise ValueError('Дата не может быть из будущего')
        return v


class FireExtinguisherCreate(FireExtinguisherBase):
    pass


class FireExtinguisherUpdate(BaseModel):
    inventory_number: Optional[str] = None
    type: Optional[str] = None
    capacity: Optional[float] = Field(None, gt=0)
    manufacturer: Optional[str] = None
    manufacture_date: Optional[date] = None
    commissioning_date: Optional[date] = None
    location_id: Optional[int] = None
    status_id: Optional[int] = None


class FireExtinguisherRead(FireExtinguisherBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------- Employees ----------

class EmployeeBase(BaseModel):
    full_name: str
    position: str


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeRead(EmployeeBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Inspections ----------

class InspectionBase(BaseModel):
    fire_extinguisher_id: int
    inspection_date: date
    employee_id: int
    pressure: Optional[float] = None
    weight: Optional[float] = None
    visual_inspection: Optional[str] = None
    seal_condition: Optional[str] = None
    safety_pin_condition: Optional[str] = None
    hose_condition: Optional[str] = None
    comments: Optional[str] = None
    next_inspection_date: date


class InspectionCreate(InspectionBase):
    pass


class InspectionRead(InspectionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# ---------- Users & Auth ----------


class UserBase(BaseModel):
    username: str
    email: str
    full_name: str
    role: str = Field(..., description="Роль: admin, engineer, viewer")


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
