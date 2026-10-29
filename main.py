# main.py (v1.3) uvicorn main:app
"""
Главный модуль приложения FireTrack.
Инициализирует FastAPI, подключает маршрутизаторы (роутеры),
настраивает статические файлы и создает базовые данные (администратора и статусы) при старте.

При работе сервера статусы огнетушителей пересчитываются автоматически:
при запуске и далее раз в час (интервал задается переменной
окружения ``STATUS_RECALC_INTERVAL_MINUTES``).
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from db import engine, Base, SessionLocal
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
from auth import get_password_hash, ROLE_ADMIN
from schemas import HealthResponse
from status_logic import ensure_default_statuses, recalculate_statuses

logger = logging.getLogger("firetrack")

BASE_DIR = Path(__file__).resolve().parent
RECALC_INTERVAL_MINUTES = int(os.getenv("STATUS_RECALC_INTERVAL_MINUTES", "60"))

# Создаем таблицы
Base.metadata.create_all(bind=engine)


def init_admin() -> None:
    """
    Создает пользователя-администратора, если в базе еще нет пользователя 'admin'.
    Пароль берется из переменной окружения ADMIN_PASSWORD (по умолчанию admin123).
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "admin").first()
        if user is None:
            password = os.getenv("ADMIN_PASSWORD", "admin123")
            if password == "admin123":
                logger.warning(
                    "Создан администратор с паролем по умолчанию admin123. "
                    "Задайте ADMIN_PASSWORD для рабочего развертывания."
                )
            admin = User(
                username="admin",
                email="admin@example.com",
                hashed_password=get_password_hash(password),
                full_name="Administrator",
                role=ROLE_ADMIN,
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
        ensure_default_statuses(db)
    finally:
        db.close()


def run_status_recalculation() -> int:
    """
    Пересчитывает статусы всего парка огнетушителей в отдельной сессии.

    Returns:
        int: Количество изменившихся статусов.
    """
    db = SessionLocal()
    try:
        return recalculate_statuses(db)
    finally:
        db.close()


async def _recalc_loop() -> None:
    """Фоновая задача: периодически пересчитывает статусы."""
    while True:
        await asyncio.sleep(RECALC_INTERVAL_MINUTES * 60)
        try:
            changed = await asyncio.to_thread(run_status_recalculation)
            if changed:
                logger.info("Автопересчет статусов: изменено %s", changed)
        except Exception:  # noqa: BLE001 - фоновая задача не должна падать
            logger.exception("Ошибка автопересчета статусов")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Действия при запуске и остановке приложения."""
    init_admin()
    init_statuses()
    run_status_recalculation()
    task = asyncio.create_task(_recalc_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(
    title="Система отметки проверки средств пожаротушения",
    description="API для управления огнетушителями и проверками",
    version="1.3.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

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
    return FileResponse(BASE_DIR / "static" / "index.html")
