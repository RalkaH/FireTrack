# schemas.py (v1.2)
"""
Модуль схем Pydantic для валидации данных, сериализации и десериализации.
Определяет структуру данных для входящих API-запросов и исходящих ответов.
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------- Health ----------

class HealthResponse(BaseModel):
    """Схема ответа для эндпоинта проверки работоспособности (Health Check)."""
    status: str


# ---------- Locations ----------

class LocationBase(BaseModel):
    """Базовая схема местоположения оборудования."""
    name: str = Field(..., description="Название места (кабинет, этаж)")
    description: Optional[str] = Field(None, description="Описание места")


class LocationCreate(LocationBase):
    """Схема для создания нового местоположения."""
    pass


class LocationRead(LocationBase):
    """Схема для чтения данных о местоположении (возвращается в API)."""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Statuses ----------

class StatusBase(BaseModel):
    """Базовая схема технического статуса огнетушителя."""
    name: str = Field(..., description="Название статуса")
    description: str = Field(..., description="Описание статуса")


class StatusCreate(StatusBase):
    """Схема для создания нового статуса."""
    pass


class StatusRead(StatusBase):
    """Схема для чтения данных о статусе (возвращается в API)."""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- FireExtinguishers ----------

class FireExtinguisherBase(BaseModel):
    """Базовая схема огнетушителя со всеми основными характеристиками."""
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
        """Валидатор: проверяет, что дата изготовления и ввода не больше текущей."""
        if v and v > date.today():
            raise ValueError('Дата не может быть из будущего')
        return v


class FireExtinguisherCreate(FireExtinguisherBase):
    """Схема для создания новой карточки огнетушителя."""
    pass


class FireExtinguisherUpdate(BaseModel):
    """Схема для частичного обновления данных огнетушителя."""
    inventory_number: Optional[str] = None
    type: Optional[str] = None
    capacity: Optional[float] = Field(None, gt=0)
    manufacturer: Optional[str] = None
    manufacture_date: Optional[date] = None
    commissioning_date: Optional[date] = None
    location_id: Optional[int] = None
    status_id: Optional[int] = None


class FireExtinguisherRead(FireExtinguisherBase):
    """Схема для чтения данных об огнетушителе (возвращается в API)."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------- Employees ----------

class EmployeeBase(BaseModel):
    """Базовая схема сотрудника компании."""
    full_name: str
    position: str


class EmployeeCreate(EmployeeBase):
    """Схема для создания нового сотрудника."""
    pass


class EmployeeRead(EmployeeBase):
    """Схема для чтения данных о сотруднике (возвращается в API)."""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Inspections ----------

class InspectionBase(BaseModel):
    """Базовая схема записи о проведенной проверке (ТО)."""
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
    """Схема для создания новой записи о проверке."""
    pass


class InspectionRead(InspectionBase):
    """Схема для чтения данных о проверке (возвращается в API)."""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# ---------- Users & Auth ----------


class UserBase(BaseModel):
    """Базовая схема данных пользователя системы."""
    username: str
    email: str
    full_name: str
    role: str = Field(..., description="Роль: admin, engineer, viewer")


class UserCreate(UserBase):
    """Схема для регистрации нового пользователя."""
    password: str


class UserRead(UserBase):
    """Схема для чтения данных пользователя (без пароля, возвращается в API)."""
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Схема JWT токена доступа."""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Схема полезной нагрузки (payload), извлеченной из JWT токена."""
    username: Optional[str] = None
