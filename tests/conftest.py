# tests/conftest.py
"""
Общие фикстуры тестов FireTrack.

Тесты работают на отдельной временной базе SQLite (создается миграциями
при старте приложения) и не трогают рабочую базу.
"""
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

_TMP_DIR = tempfile.mkdtemp(prefix="firetrack-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP_DIR) / 'test.db'}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ADMIN_PASSWORD"] = "Adm1n-Test-Pass"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

import migrate  # noqa: E402

# Резервные копии перед миграциями в тестах кладем во временную папку
migrate.BACKUP_DIR = Path(_TMP_DIR) / "backups"

from main import app  # noqa: E402

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
USER_PASSWORD = "Str0ng-Pass-42"


@pytest.fixture(scope="session")
def tmp_dir() -> Path:
    """Временная папка тестов."""
    return Path(_TMP_DIR)


@pytest.fixture(scope="session")
def client():
    """Клиент приложения (lifespan выполняется: миграции, админ, статусы)."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_throttle():
    """Ограничение попыток входа не должно переходить из теста в тест."""
    import auth
    auth.login_throttle.reset()
    yield
    auth.login_throttle.reset()


def login(client, username: str, password: str) -> dict:
    """Входит и возвращает заголовки с токеном."""
    resp = client.post("/auth/token", data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture(scope="session")
def headers(client) -> dict:
    """Заголовки администратора."""
    return login(client, "admin", ADMIN_PASSWORD)


@pytest.fixture
def make_user(client, headers):
    """
    Фабрика пользователей: создает пользователя через API и возвращает
    (данные пользователя, заголовки с его токеном).
    """
    def _make(role: str = "engineer", must_change_password: bool = False):
        username = f"{role[:4]}_{uuid.uuid4().hex[:8]}"
        resp = client.post("/users/", headers=headers, json={
            "username": username, "full_name": f"Тест {role}",
            "email": f"{username}@example.com", "role": role,
            "password": USER_PASSWORD, "must_change_password": must_change_password,
        })
        assert resp.status_code == 201, resp.text
        return resp.json(), login(client, username, USER_PASSWORD)
    return _make


def status_id(client, headers, name: str) -> int:
    """ID статуса по названию."""
    statuses = client.get("/statuses/", headers=headers).json()
    return next(s["id"] for s in statuses if s["name"] == name)


@pytest.fixture(scope="session")
def base_refs(client, headers) -> dict:
    """Место и сотрудник, общие для тестов."""
    loc = client.post("/locations/", json={"name": f"Склад {uuid.uuid4().hex[:6]}"}, headers=headers)
    assert loc.status_code == 201, loc.text
    emp = client.post("/employees/", json={"full_name": "Петров П. П.", "position": "Инженер"},
                      headers=headers)
    assert emp.status_code == 201, emp.text
    return {"location_id": loc.json()["id"], "location": loc.json()["name"],
            "employee_id": emp.json()["id"]}


@pytest.fixture
def make_extinguisher(client, headers, base_refs):
    """Фабрика огнетушителей с уникальным номером."""
    def _make(**fields):
        data = {
            "inventory_number": f"Т-{uuid.uuid4().hex[:8]}", "type": "ОП-5", "capacity": 5,
            "location_id": base_refs["location_id"],
            "status_id": status_id(client, headers, "Актуально"),
        }
        data.update(fields)
        resp = client.post("/extinguishers/", headers=headers, json=data)
        assert resp.status_code == 201, resp.text
        return resp.json()
    return _make
