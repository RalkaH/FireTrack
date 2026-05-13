# db.py (v1.1)
"""
Модуль для настройки подключения к базе данных SQLAlchemy.
Обеспечивает создание движка, сессий и базового класса для моделей.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Получаем URL базы данных из переменных окружения или используем SQLite по умолчанию
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fire_extinguishers.db")


class Base(DeclarativeBase):
    """Базовый класс для всех моделей базы данных."""
    pass


# Настройка движка (для SQLite отключаем проверку потоков)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith(
        "sqlite") else {},
)

# Фабрика сессий для взаимодействия с БД
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Генератор для получения сессии базы данных.
    Используется как зависимость в эндпоинтах FastAPI.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
