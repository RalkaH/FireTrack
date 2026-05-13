# main.py (v1.2) uvicorn main:app
"""
Главный модуль приложения FireTrack.
Инициализирует FastAPI, подключает маршрутизаторы (роутеры),
настраивает статические файлы и создает базовые данные (администратора и статусы) при старте.
"""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from models import Status

from db import engine, Base, SessionLocal
import models
from models import User
from routers import (
    locations,
    statuses,
    extinguishers,
    employees,
    inspections,
    reports,
    import_data,
)
import auth as auth_router
from schemas import HealthResponse
from auth import get_password_hash


# Создаем таблицы
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Система отметки проверки средств пожаротушения",
    description="API для управления огнетушителями и проверками",
    version="1.0.0",
)

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")


def init_admin() -> None:
    """
    Создает пользователя администратора по умолчанию (admin/admin123),
    если в базе данных еще нет пользователя с логином 'admin'.
    Выполняется при запуске приложения.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "admin").first()
        if user is None:
            admin = User(
                username="admin",
                email="admin@example.com",
                hashed_password=get_password_hash("admin123"),
                full_name="Administrator",
                role="admin",
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()


def init_statuses() -> None:
    """
    Инициализирует стандартные статусы огнетушителей в базе данных,
    если они отсутствуют. Включает статусы: Актуально, Просрочено,
    Требует обслуживания, На техническом обслуживании, Списан.
    """
    db = SessionLocal()
    try:
        defaults = [
            {"name": "Актуально",
                "description": "Огнетушитель прошел проверку, срок не истек"},
            {"name": "Просрочено", "description": "Необходима проверка, срок истек"},
            {"name": "Требует обслуживания",
                "description": "Обнаружены дефекты при проверке"},
            {"name": "На техническом обслуживании",
                "description": "Огнетушитель на ТО"},
            {"name": "Списан", "description": "Огнетушитель выведен из эксплуатации"},
        ]
        for item in defaults:
            exists = db.query(Status).filter(
                Status.name == item["name"]).first()
            if exists is None:
                st = Status(
                    name=item["name"],
                    description=item["description"],
                    created_at=datetime.now(timezone.utc),
                )
                db.add(st)
        db.commit()
    finally:
        db.close()


init_admin()
init_statuses()

# Подключаем роутеры API
app.include_router(locations.router)
app.include_router(statuses.router)
app.include_router(employees.router)
app.include_router(extinguishers.router)
app.include_router(inspections.router)
app.include_router(reports.router)
app.include_router(import_data.router)
app.include_router(auth_router.router)


# Health check
@app.get("/health", response_model=HealthResponse)
def health_check():
    """
    Эндпоинт для проверки работоспособности (Health Check) API.

    Returns:
        dict: Словарь со статусом 'ok', если сервер работает.
    """
    return {"status": "ok"}


# Главная страница
@app.get("/")
async def read_root():
    """
    Отдает главную страницу Frontend-приложения (index.html).

    Returns:
        FileResponse: HTML-файл интерфейса системы.
    """
    return FileResponse(Path("static") / "index.html")
