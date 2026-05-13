# main.py (v1.1)
# uvicorn main:app

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
    """Создать пользователя admin/admin123, если его ещё нет."""
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
    """Создать стандартные статусы, если их ещё нет."""
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
    return {"status": "ok"}


# Главная страница
@app.get("/")
async def read_root():
    return FileResponse(Path("static") / "index.html")
