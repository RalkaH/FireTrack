# tests/test_api.py
"""
Интеграционные тесты API FireTrack.

Запуск из корня проекта:  python -m pytest -q
Тесты используют отдельную временную базу SQLite и не трогают рабочую.
"""
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

_TMP_DIR = tempfile.mkdtemp(prefix="firetrack-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP_DIR) / 'test.db'}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ADMIN_PASSWORD"] = "admin123"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

import auth  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def headers(client):
    resp = client.post("/auth/token", data={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["expires_in"] > 0
    return {"Authorization": f"Bearer {body['access_token']}"}


def _status_id(client, headers, name):
    statuses = client.get("/statuses/", headers=headers).json()
    return next(s["id"] for s in statuses if s["name"] == name)


def test_endpoints_require_auth(client):
    for path in ["/locations/", "/employees/", "/statuses/", "/inspections/",
                 "/extinguishers/", "/reports/dashboard", "/reports/upcoming",
                 "/reports/expired", "/auth/me"]:
        assert client.get(path).status_code == 401, path
    assert client.post("/statuses/recalculate").status_code == 401


def test_expired_token_rejected(client):
    token = auth.create_access_token({"sub": "admin"}, expires_delta=timedelta(minutes=-1))
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_me(client, headers):
    resp = client.get("/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_viewer_cannot_modify(client, headers):
    from db import SessionLocal
    from models import User
    from datetime import datetime, timezone

    db = SessionLocal()
    db.add(User(username="viewer", email="v@example.com",
                hashed_password=auth.get_password_hash("viewer1"),
                full_name="Viewer", role="viewer", is_active=True,
                created_at=datetime.now(timezone.utc)))
    db.commit()
    db.close()

    token = client.post("/auth/token", data={"username": "viewer", "password": "viewer1"}).json()["access_token"]
    vh = {"Authorization": f"Bearer {token}"}
    assert client.get("/locations/", headers=vh).status_code == 200
    assert client.post("/locations/", json={"name": "X"}, headers=vh).status_code == 403


def test_full_flow(client, headers):
    loc = client.post("/locations/", json={"name": "Кабинет 101"}, headers=headers)
    assert loc.status_code == 201, loc.text
    emp = client.post("/employees/", json={"full_name": "Иванов И. И.", "position": "Инженер"}, headers=headers)
    assert emp.status_code == 201

    actual = _status_id(client, headers, "Актуально")
    ext = client.post("/extinguishers/", headers=headers, json={
        "inventory_number": "ОУ-001", "type": "ОУ-5", "capacity": 5,
        "location_id": loc.json()["id"], "status_id": actual,
    })
    assert ext.status_code == 201, ext.text
    ext_id = ext.json()["id"]

    # Пустые даты при редактировании допустимы (очищают поле)
    upd = client.put(f"/extinguishers/{ext_id}", headers=headers,
                     json={"manufacture_date": None, "manufacturer": None})
    assert upd.status_code == 200, upd.text

    # Две проверки: старая (срок скоро) и свежая. В предстоящих должна быть одна запись
    today = date.today()
    old = client.post("/inspections/", headers=headers, json={
        "fire_extinguisher_id": ext_id, "employee_id": emp.json()["id"],
        "inspection_date": (today - timedelta(days=170)).isoformat(),
        "next_inspection_date": (today + timedelta(days=10)).isoformat(),
    })
    assert old.status_code == 201, old.text
    new = client.post("/inspections/", headers=headers, json={
        "fire_extinguisher_id": ext_id, "employee_id": emp.json()["id"],
        "inspection_date": today.isoformat(),
        "next_inspection_date": (today + timedelta(days=20)).isoformat(),
    })
    assert new.status_code == 201

    upcoming = client.get("/reports/upcoming?days=30", headers=headers).json()
    assert len(upcoming) == 1
    assert upcoming[0]["days_until_inspection"] == 20
    dash = client.get("/reports/dashboard", headers=headers).json()
    assert dash["upcoming_inspections_30_days"] == 1

    # Дата следующей проверки считается автоматически
    auto = client.post("/inspections/", headers=headers, json={
        "fire_extinguisher_id": ext_id, "employee_id": emp.json()["id"],
        "inspection_date": today.isoformat(),
    })
    assert auto.status_code == 201, auto.text
    assert auto.json()["next_inspection_date"] == (today + timedelta(days=180)).isoformat()

    # Дефект при осмотре -> «Требует обслуживания»
    client.post("/inspections/", headers=headers, json={
        "fire_extinguisher_id": ext_id, "employee_id": emp.json()["id"],
        "inspection_date": today.isoformat(), "seal_condition": "Отсутствует",
    })
    fe = client.get(f"/extinguishers/{ext_id}", headers=headers).json()
    assert fe["status_id"] == _status_id(client, headers, "Требует обслуживания")

    # Списанный огнетушитель не меняет статус при пересчете
    decom = _status_id(client, headers, "Списан")
    client.put(f"/extinguishers/{ext_id}", headers=headers, json={"status_id": decom})
    assert client.post("/statuses/recalculate", headers=headers).status_code == 200
    fe = client.get(f"/extinguishers/{ext_id}", headers=headers).json()
    assert fe["status_id"] == decom


def test_inspection_validation(client, headers):
    today = date.today()
    resp = client.post("/inspections/", headers=headers, json={
        "fire_extinguisher_id": 1, "employee_id": 1,
        "inspection_date": (today + timedelta(days=1)).isoformat(),
    })
    assert resp.status_code == 422
    resp = client.post("/inspections/", headers=headers, json={
        "fire_extinguisher_id": 1, "employee_id": 1,
        "inspection_date": today.isoformat(),
        "next_inspection_date": (today - timedelta(days=1)).isoformat(),
    })
    assert resp.status_code == 422


def test_expired_and_recalculate(client, headers):
    actual = _status_id(client, headers, "Актуально")
    loc_id = client.get("/locations/", headers=headers).json()[0]["id"]
    emp_id = client.get("/employees/", headers=headers).json()[0]["id"]
    ext = client.post("/extinguishers/", headers=headers, json={
        "inventory_number": "ОП-777", "type": "ОП-4", "capacity": 4,
        "location_id": loc_id, "status_id": actual,
    }).json()
    today = date.today()
    client.post("/inspections/", headers=headers, json={
        "fire_extinguisher_id": ext["id"], "employee_id": emp_id,
        "inspection_date": (today - timedelta(days=200)).isoformat(),
        "next_inspection_date": (today - timedelta(days=5)).isoformat(),
    })
    expired = client.get("/reports/expired", headers=headers).json()
    item = next(e for e in expired if e["inventory_number"] == "ОП-777")
    assert item["days_overdue"] == 5


def test_import_reports_bad_rows(client, headers):
    csv_text = (
        "inventory_number;type;capacity;manufacturer;manufacture_date;commissioning_date;location_name;status_name\n"
        "ИМП-1;ОУ-2;2;;2023-01-01;;Кабинет 101;Актуально\n"
        "ИМП-1;ОУ-2;2;;2023-01-01;;Кабинет 101;Актуально\n"
        "ИМП-2;ОУ-2;2;;01/01/2023;;Кабинет 101;Актуально\n"
        "ИМП-3;ОУ-2;abc;;;;Кабинет 101;\n"
    )
    resp = client.post("/import/extinguishers", headers=headers,
                       files={"file": ("import.csv", csv_text.encode("cp1251"), "text/csv")})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] == 1
    assert len(body["errors"]) == 3


def test_import_missing_columns(client, headers):
    resp = client.post("/import/locations", headers=headers,
                       files={"file": ("import.csv", "title;x\nA;B\n".encode(), "text/csv")})
    assert resp.status_code == 400
