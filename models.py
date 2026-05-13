# models.py (v1.1)
"""
Модуль описания ORM-моделей системы FireTrack.
Определяет таблицы для локаций, статусов, огнетушителей, сотрудников, проверок и пользователей.
"""
from sqlalchemy import Column, Integer, String, Date, DateTime, Float, ForeignKey
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
    """Модель единицы противопожарного оборудования (огнетушителя)."""
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
    """Модель пользователя системы для авторизации и управления правами доступа."""
    __tablename__ = "Users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False)  # "admin", "engineer", "viewer"
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, nullable=False)
