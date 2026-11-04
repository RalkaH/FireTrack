# models.py (v1.2)
"""
Модуль описания ORM-моделей системы FireTrack.
Определяет таблицы для локаций, статусов, огнетушителей, сотрудников, проверок,
пользователей, журнала действий и настроек.

Схема базы меняется только через миграции Alembic (папка ``migrations``).
Если добавляете колонку здесь, создайте для нее новую ревизию.
"""
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship
from db import Base


class Location(Base):
    """Модель местоположения (помещения, этажи) оборудования."""
    __tablename__ = "Locations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False)

    fire_extinguishers = relationship(
        "FireExtinguisher", back_populates="location")


class Status(Base):
    """Модель технических статусов огнетушителей (Актуально, Списан и т.д.)."""
    __tablename__ = "Statuses"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)

    fire_extinguishers = relationship(
        "FireExtinguisher", back_populates="status")


class FireExtinguisher(Base):
    """
    Модель единицы противопожарного оборудования (огнетушителя).

    Кроме плановых осмотров у огнетушителя есть сроки перезарядки и срок
    службы. Интервалы по умолчанию зависят от вида огнетушащего вещества
    и задаются в настройках (модуль ``deadlines``). Колонки
    ``recharge_interval_months`` и ``service_life_years`` позволяют
    переопределить их для конкретного экземпляра (например, по паспорту).
    """
    __tablename__ = "FireExtinguishers"
    id = Column(Integer, primary_key=True, index=True)
    inventory_number = Column(String, unique=True, nullable=False)
    type = Column(String, nullable=False)
    capacity = Column(Float, nullable=False)
    manufacturer = Column(String, nullable=True)
    manufacture_date = Column(Date, nullable=True)
    commissioning_date = Column(Date, nullable=True)
    location_id = Column(Integer, ForeignKey("Locations.id"), nullable=False)
    status_id = Column(Integer, ForeignKey("Statuses.id"), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    last_recharge_date = Column(Date, nullable=True)
    recharge_interval_months = Column(Integer, nullable=True)
    service_life_years = Column(Integer, nullable=True)

    location = relationship("Location", back_populates="fire_extinguishers")
    status = relationship("Status", back_populates="fire_extinguishers")
    inspections = relationship(
        "Inspection", back_populates="fire_extinguisher")


class Employee(Base):
    """Модель сотрудника, ответственного за проведение проверок."""
    __tablename__ = "Employees"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    position = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)

    inspections = relationship("Inspection", back_populates="employee")


class Inspection(Base):
    """Модель записи о проведенной проверке оборудования."""
    __tablename__ = "Inspections"
    id = Column(Integer, primary_key=True, index=True)
    fire_extinguisher_id = Column(Integer, ForeignKey(
        "FireExtinguishers.id"), nullable=False)
    inspection_date = Column(Date, nullable=False)
    employee_id = Column(Integer, ForeignKey("Employees.id"), nullable=False)
    pressure = Column(Float, nullable=True)
    weight = Column(Float, nullable=True)
    visual_inspection = Column(String, nullable=True)
    seal_condition = Column(String, nullable=True)
    safety_pin_condition = Column(String, nullable=True)
    hose_condition = Column(String, nullable=True)
    comments = Column(String, nullable=True)
    next_inspection_date = Column(Date, nullable=False)
    created_at = Column(DateTime, nullable=False)

    fire_extinguisher = relationship(
        "FireExtinguisher", back_populates="inspections")
    employee = relationship("Employee", back_populates="inspections")


class User(Base):
    """
    Модель пользователя системы для авторизации и управления правами доступа.

    ``token_version`` входит в каждый выданный JWT. Смена или сброс пароля
    и блокировка увеличивают его, и все старые токены пользователя
    сразу перестают работать.
    """
    __tablename__ = "Users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False)  # "admin", "engineer", "viewer"
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, nullable=False)
    must_change_password = Column(
        Boolean, nullable=False, default=False, server_default=text("0"))
    token_version = Column(
        Integer, nullable=False, default=0, server_default=text("0"))
    last_login_at = Column(DateTime, nullable=True)


class AuditLog(Base):
    """
    Запись журнала действий пользователей.

    Логин хранится строкой, поэтому запись остается понятной, даже если
    пользователя потом переименуют или удалят. Пароли и хеши сюда
    никогда не попадают.
    """
    __tablename__ = "AuditLog"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, nullable=False, index=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String, nullable=True, index=True)
    action = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=True, index=True)
    entity_id = Column(Integer, nullable=True)
    summary = Column(String, nullable=False)
    changes = Column(Text, nullable=True)  # JSON: {"поле": {"old": ..., "new": ...}}
    ip = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)


class AppSetting(Base):
    """Настройка приложения в виде пары «ключ — значение» (строкой)."""
    __tablename__ = "Settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=True)
    updated_at = Column(DateTime, nullable=False)
