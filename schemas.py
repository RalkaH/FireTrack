# schemas.py (v1.4)
"""
Модуль схем Pydantic для валидации данных, сериализации и десериализации.
Определяет структуру данных для входящих API-запросов и исходящих ответов.
"""
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _date_not_in_future(value: Optional[date]) -> Optional[date]:
    """Проверяет, что дата не позже сегодняшнего дня."""
    if value and value > date.today():
        raise ValueError("Дата не может быть из будущего")
    return value


# ---------- Health ----------

class HealthResponse(BaseModel):
    """Схема ответа для эндпоинта проверки работоспособности (Health Check)."""
    status: str


# ---------- Locations ----------

class LocationBase(BaseModel):
    """Базовая схема местоположения оборудования."""
    name: str = Field(..., min_length=1, description="Название места (кабинет, этаж)")
    description: Optional[str] = Field(None, description="Описание места")


class LocationCreate(LocationBase):
    """Схема для создания нового местоположения."""
    pass


class LocationRead(LocationBase):
    """Схема для чтения данных о местоположении (возвращается в API)."""
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Statuses ----------

class StatusBase(BaseModel):
    """Базовая схема технического статуса огнетушителя."""
    name: str = Field(..., min_length=1, description="Название статуса")
    description: str = Field(..., description="Описание статуса")


class StatusCreate(StatusBase):
    """Схема для создания нового статуса."""
    pass


class StatusRead(StatusBase):
    """Схема для чтения данных о статусе (возвращается в API)."""
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- FireExtinguishers ----------

class FireExtinguisherBase(BaseModel):
    """Базовая схема огнетушителя со всеми основными характеристиками."""
    inventory_number: str = Field(..., min_length=1, description="Инвентарный номер")
    type: str = Field(..., min_length=1, description="Тип огнетушителя (ОУ-8 и т.п.)")
    capacity: float = Field(..., gt=0, description="Вместимость (л / кг)")
    manufacturer: Optional[str] = Field(None, description="Производитель")
    manufacture_date: Optional[date] = Field(
        None, description="Дата изготовления")
    commissioning_date: Optional[date] = Field(
        None, description="Дата ввода в эксплуатацию")
    location_id: int = Field(..., description="ID места (Locations.id)")
    status_id: int = Field(..., description="ID статуса (Statuses.id)")
    last_recharge_date: Optional[date] = Field(
        None, description="Дата последней перезарядки")
    recharge_interval_months: Optional[int] = Field(
        None, ge=1, le=240,
        description="Интервал перезарядки, мес. Пусто: по виду ОТВ из настроек")
    service_life_years: Optional[int] = Field(
        None, ge=1, le=50,
        description="Срок службы, лет. Пусто: значение из настроек")

    @field_validator('manufacture_date', 'commissioning_date', 'last_recharge_date')
    @classmethod
    def not_in_future(cls, v):
        """Валидатор: даты изготовления, ввода и перезарядки не больше текущей."""
        return _date_not_in_future(v)


class FireExtinguisherCreate(FireExtinguisherBase):
    """Схема для создания новой карточки огнетушителя."""
    pass


class FireExtinguisherUpdate(BaseModel):
    """Схема для частичного обновления данных огнетушителя."""
    inventory_number: Optional[str] = Field(None, min_length=1)
    type: Optional[str] = Field(None, min_length=1)
    capacity: Optional[float] = Field(None, gt=0)
    manufacturer: Optional[str] = None
    manufacture_date: Optional[date] = None
    commissioning_date: Optional[date] = None
    location_id: Optional[int] = None
    status_id: Optional[int] = None
    last_recharge_date: Optional[date] = None
    recharge_interval_months: Optional[int] = Field(None, ge=1, le=240)
    service_life_years: Optional[int] = Field(None, ge=1, le=50)

    @field_validator('manufacture_date', 'commissioning_date', 'last_recharge_date')
    @classmethod
    def not_in_future(cls, v):
        """Валидатор: даты изготовления, ввода и перезарядки не могут быть из будущего."""
        return _date_not_in_future(v)


class FireExtinguisherRead(FireExtinguisherBase):
    """
    Схема для чтения данных об огнетушителе (возвращается в API).

    Поля сроков (вид ОТВ, следующая перезарядка, конец срока службы)
    вычисляются сервером, хранить их не нужно.
    """
    id: int
    created_at: datetime
    updated_at: datetime
    agent_label: Optional[str] = Field(None, description="Вид ОТВ по типу")
    effective_recharge_interval_months: Optional[int] = None
    next_recharge_date: Optional[date] = None
    recharge_days_left: Optional[int] = None
    recharge_state: Optional[str] = Field(None, description="ok, soon, overdue, unknown")
    effective_service_life_years: Optional[int] = None
    service_end_date: Optional[date] = None
    service_state: Optional[str] = Field(None, description="ok, soon, overdue, unknown")

    model_config = ConfigDict(from_attributes=True)


# ---------- Employees ----------

class EmployeeBase(BaseModel):
    """Базовая схема сотрудника компании."""
    full_name: str = Field(..., min_length=1)
    position: str = Field(..., min_length=1)


class EmployeeCreate(EmployeeBase):
    """Схема для создания нового сотрудника."""
    pass


class EmployeeRead(EmployeeBase):
    """Схема для чтения данных о сотруднике (возвращается в API)."""
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
    next_inspection_date: Optional[date] = Field(
        None,
        description="Дата следующей проверки. Если не указана, "
                    "рассчитывается автоматически (+6 месяцев)",
    )


class InspectionCreate(InspectionBase):
    """Схема для создания новой записи о проверке."""

    @field_validator('inspection_date')
    @classmethod
    def inspection_not_in_future(cls, v):
        """Валидатор: дата проверки не может быть из будущего."""
        return _date_not_in_future(v)

    @model_validator(mode='after')
    def next_after_inspection(self):
        """Валидатор: следующая проверка не может быть раньше текущей."""
        if self.next_inspection_date and self.next_inspection_date < self.inspection_date:
            raise ValueError(
                "Дата следующей проверки не может быть раньше даты проверки")
        return self


class InspectionRead(InspectionBase):
    """Схема для чтения данных о проверке (возвращается в API)."""
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ---------- Users & Auth ----------

ROLES = ("admin", "engineer", "viewer")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MIN_LENGTH = 8
WEAK_PASSWORDS = {"admin123", "password", "12345678", "123456789", "qwerty123",
                  "11111111", "password1", "firetrack", "qwertyui"}


def validate_password_strength(password: str, username: Optional[str] = None) -> str:
    """
    Проверяет, что пароль достаточно надежный.

    Args:
        password (str): Новый пароль.
        username (Optional[str]): Логин (пароль не должен с ним совпадать).

    Returns:
        str: Тот же пароль.

    Raises:
        ValueError: Если пароль короче 8 символов, совпадает с логином
            или входит в список самых частых паролей.
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Пароль должен быть не короче {PASSWORD_MIN_LENGTH} символов")
    if password.lower() in WEAK_PASSWORDS:
        raise ValueError("Слишком простой пароль")
    if username and password.lower() == username.lower():
        raise ValueError("Пароль не должен совпадать с логином")
    return password


def _check_role(value: str) -> str:
    """Проверяет, что роль из списка ROLES."""
    if value not in ROLES:
        raise ValueError("Роль должна быть одной из: " + ", ".join(ROLES))
    return value


def _check_email(value: str) -> str:
    """Проверяет формат email."""
    value = value.strip()
    if not EMAIL_RE.match(value):
        raise ValueError("Некорректный email")
    return value


def _check_full_name(value: Optional[str]) -> Optional[str]:
    """ФИО не может состоять из одних пробелов."""
    if value is None:
        return value
    value = value.strip()
    if not value:
        raise ValueError("Укажите ФИО")
    return value


class UserBase(BaseModel):
    """Базовая схема данных пользователя системы."""
    username: str
    email: str
    full_name: str
    role: str = Field(..., description="Роль: admin, engineer, viewer")


class UserCreate(UserBase):
    """Схема создания пользователя администратором."""
    password: str
    must_change_password: bool = Field(
        True, description="Потребовать смену пароля при первом входе")

    @field_validator("username")
    @classmethod
    def username_format(cls, v):
        """Логин: 3-32 символа, латиница, цифры и знаки _ . -"""
        v = v.strip()
        if not USERNAME_RE.match(v):
            raise ValueError("Логин: от 3 до 32 символов, латиница, цифры, _ . -")
        return v

    @field_validator("full_name")
    @classmethod
    def full_name_required(cls, v):
        """ФИО не может быть пустым."""
        return _check_full_name(v)

    @field_validator("email")
    @classmethod
    def email_format(cls, v):
        """Проверка формата email."""
        return _check_email(v)

    @field_validator("role")
    @classmethod
    def role_known(cls, v):
        """Роль должна быть из списка."""
        return _check_role(v)

    @model_validator(mode="after")
    def strong_password(self):
        """Проверка надежности пароля."""
        validate_password_strength(self.password, self.username)
        return self


class UserUpdate(BaseModel):
    """Схема изменения пользователя администратором (без пароля)."""
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def full_name_required(cls, v):
        """ФИО не может быть пустым."""
        return _check_full_name(v)

    @field_validator("email")
    @classmethod
    def email_format(cls, v):
        """Проверка формата email."""
        return _check_email(v) if v is not None else v

    @field_validator("role")
    @classmethod
    def role_known(cls, v):
        """Роль должна быть из списка."""
        return _check_role(v) if v is not None else v


class UserStatusUpdate(BaseModel):
    """Блокировка или разблокировка пользователя."""
    is_active: bool


class PasswordReset(BaseModel):
    """Сброс пароля администратором."""
    new_password: str


class PasswordChange(BaseModel):
    """Смена собственного пароля."""
    old_password: str
    new_password: str


class UserRead(UserBase):
    """Схема для чтения данных пользователя (без пароля, возвращается в API)."""
    id: int
    is_active: bool
    created_at: datetime
    must_change_password: bool = False
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """Схема JWT токена доступа."""
    access_token: str
    token_type: str
    expires_in: Optional[int] = Field(None, description="Время жизни токена, сек")
    must_change_password: bool = False


class TokenData(BaseModel):
    """Схема полезной нагрузки (payload), извлеченной из JWT токена."""
    username: Optional[str] = None


# ---------- Audit ----------

class AuditRead(BaseModel):
    """Запись журнала действий."""
    id: int
    created_at: datetime
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    summary: str
    changes: Optional[Dict[str, Any]] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None


class AuditPage(BaseModel):
    """Страница журнала действий."""
    items: List[AuditRead]
    total: int
    page: int
    page_size: int


# ---------- Recharge ----------

class RechargeMark(BaseModel):
    """Отметка о перезарядке огнетушителя."""
    recharge_date: date = Field(..., description="Дата перезарядки")
    recharge_interval_months: Optional[int] = Field(
        None, ge=1, le=240, description="Новый интервал по паспорту, мес. (если изменился)")
    comment: Optional[str] = Field(None, max_length=200, description="Кто перезаряжал, номер акта")

    @field_validator("recharge_date")
    @classmethod
    def not_in_future(cls, v):
        """Дата перезарядки не может быть из будущего."""
        return _date_not_in_future(v)
