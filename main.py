# main.py (v1.5) uvicorn main:app
"""
Главный модуль приложения FireTrack.
Инициализирует FastAPI, подключает маршрутизаторы (роутеры),
настраивает статические файлы и создает базовые данные (администратора и статусы) при старте.

При запуске схема базы доводится до последней версии миграциями Alembic
(см. ``migrate.py``), перед изменениями делается резервная копия базы.

При работе сервера статусы огнетушителей пересчитываются автоматически:
при запуске и далее раз в час (интервал задается переменной
окружения ``STATUS_RECALC_INTERVAL_MINUTES``). Раз в сутки делается
резервная копия базы (см. ``backup.py``).
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import backup
from app_settings import get_settings
from db import SessionLocal
from migrate import upgrade_database
from models import User
from routers import (
    locations,
    statuses,
    extinguishers,
    employees,
    inspections,
    reports,
    import_data,
    users,
    audit_log,
    settings,
    service_records,
    backups,
)
import auth as auth_router
from auth import DEFAULT_ADMIN_PASSWORD, ROLE_ADMIN, get_password_hash, verify_password
from schemas import HealthResponse
from status_logic import ensure_default_statuses, recalculate_statuses

logger = logging.getLogger("firetrack")

BASE_DIR = Path(__file__).resolve().parent
RECALC_INTERVAL_MINUTES = int(os.getenv("STATUS_RECALC_INTERVAL_MINUTES", "60"))
BACKUP_CHECK_INTERVAL_SECONDS = 3600

# Интерфейс не загружает ничего со сторонних сайтов и работает без интернета.
# 'unsafe-inline' нужен обработчикам onclick и встроенным стилям.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; "
    "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)
# Встроенная документация API грузит Swagger и ReDoc с CDN
CSP_EXEMPT_PATHS = ("/docs", "/redoc")


def init_admin() -> None:
    """
    Создает пользователя-администратора, если в базе еще нет пользователя 'admin'.
    Пароль берется из переменной окружения ADMIN_PASSWORD (по умолчанию admin123).

    Если у администратора пароль по умолчанию (только что созданный или
    оставшийся с прошлых версий), ему ставится обязательная смена пароля
    при следующем входе.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "admin").first()
        if user is None:
            password = os.getenv("ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
            if password == DEFAULT_ADMIN_PASSWORD:
                logger.warning(
                    "Создан администратор с паролем по умолчанию admin123. "
                    "При первом входе система попросит его сменить."
                )
            admin = User(
                username="admin",
                email="admin@example.com",
                hashed_password=get_password_hash(password),
                full_name="Administrator",
                role=ROLE_ADMIN,
                is_active=True,
                created_at=datetime.now(timezone.utc),
                must_change_password=password == DEFAULT_ADMIN_PASSWORD,
            )
            db.add(admin)
            db.commit()
        elif not user.must_change_password and verify_password(
                DEFAULT_ADMIN_PASSWORD, user.hashed_password):
            user.must_change_password = True
            db.commit()
            logger.warning("У администратора пароль по умолчанию: при входе потребуется его сменить.")
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


def run_scheduled_backup() -> None:
    """Делает суточную копию базы. Ошибка копии не должна мешать работе сервера."""
    db = SessionLocal()
    try:
        keep = int(get_settings(db)["backup_keep_count"])
    finally:
        db.close()
    try:
        backup.run_scheduled_backup(keep)
    except Exception:  # noqa: BLE001 - сервер должен работать и без копии
        logger.exception("Не удалось создать автокопию базы")


async def _backup_loop() -> None:
    """Фоновая задача: раз в час проверяет, пора ли делать суточную копию."""
    while True:
        await asyncio.sleep(BACKUP_CHECK_INTERVAL_SECONDS)
        await asyncio.to_thread(run_scheduled_backup)


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
    upgrade_database()
    init_admin()
    init_statuses()
    run_status_recalculation()
    run_scheduled_backup()
    tasks = [asyncio.create_task(_recalc_loop()), asyncio.create_task(_backup_loop())]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()


app = FastAPI(
    title="Система отметки проверки средств пожаротушения",
    description="API для управления огнетушителями и проверками",
    version="1.5.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """
    Добавляет заголовки безопасности ко всем ответам.

    Args:
        request (Request): Запрос.
        call_next: Следующий обработчик.

    Returns:
        Response: Ответ с заголовками.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    if not request.url.path.startswith(CSP_EXEMPT_PATHS):
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    if not request.url.path.startswith("/static"):
        # Данные API не должны оседать в кэше браузера
        response.headers["Cache-Control"] = "no-store"
    return response


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Подключаем роутеры API
app.include_router(locations.router)
app.include_router(statuses.router)
app.include_router(employees.router)
app.include_router(extinguishers.router)
app.include_router(inspections.router)
app.include_router(reports.router)
app.include_router(import_data.router)
app.include_router(users.router)
app.include_router(audit_log.router)
app.include_router(settings.router)
app.include_router(service_records.router)
app.include_router(backups.router)
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


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Значок приложения."""
    return FileResponse(BASE_DIR / "static" / "favicon.ico")


# Главная страница
@app.get("/")
async def read_root():
    """
    Отдает главную страницу Frontend-приложения (index.html).

    Returns:
        FileResponse: HTML-файл интерфейса системы.
    """
    return FileResponse(BASE_DIR / "static" / "index.html")
