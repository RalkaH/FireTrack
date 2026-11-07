# tests/test_api.py
"""
Интеграционные тесты основного API FireTrack.

Запуск из корня проекта:  python -m pytest -q
Тесты используют отдельную временную базу SQLite и не трогают рабочую.
"""
from datetime import date, timedelta

import auth
from conftest import status_id
from deadlines import add_months


def test_endpoints_require_auth(client):
    for path in ["/locations/", "/employees/", "/statuses/", "/inspections/",
                 "/extinguishers/", "/reports/dashboard", "/reports/upcoming",
                 "/reports/expired", "/reports/recharge", "/reports/journal.xlsx",
                 "/reports/print/fleet", "/auth/me", "/users/", "/audit/", "/settings/",
                 "/import/templates/locations"]:
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
    assert resp.json()["must_change_password"] is False


def test_viewer_cannot_modify(client, make_user):
    _, vh = make_user("viewer")
    assert client.get("/locations/", headers=vh).status_code == 200
    assert client.post("/locations/", json={"name": "X"}, headers=vh).status_code == 403


def test_full_flow(client, headers):
    loc = client.post("/locations/", json={"name": "Кабинет 101"}, headers=headers)
    assert loc.status_code == 201, loc.text
    emp = client.post("/employees/", json={"full_name": "Иванов И. И.", "position": "Инженер"}, headers=headers)
    assert emp.status_code == 201

    actual = status_id(client, headers, "Актуально")
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
    mine = [u for u in upcoming if u["inventory_number"] == "ОУ-001"]
    assert len(mine) == 1
    assert mine[0]["days_until_inspection"] == 20
    dash = client.get("/reports/dashboard", headers=headers).json()
    assert dash["upcoming_inspections_30_days"] >= 1

    # Дата следующей проверки считается автоматически
    auto = client.post("/inspections/", headers=headers, json={
        "fire_extinguisher_id": ext_id, "employee_id": emp.json()["id"],
        "inspection_date": today.isoformat(),
    })
    assert auto.status_code == 201, auto.text
    # По умолчанию ежегодно: п. 5.1.1 ГОСТ Р 59641-2021
    assert auto.json()["next_inspection_date"] == add_months(today, 12).isoformat()

    # Дефект при осмотре -> «Требует обслуживания»
    client.post("/inspections/", headers=headers, json={
        "fire_extinguisher_id": ext_id, "employee_id": emp.json()["id"],
        "inspection_date": today.isoformat(), "seal_condition": "Отсутствует",
    })
    fe = client.get(f"/extinguishers/{ext_id}", headers=headers).json()
    assert fe["status_id"] == status_id(client, headers, "Требует обслуживания")

    # Списанный огнетушитель не меняет статус при пересчете
    decom = status_id(client, headers, "Списан")
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


def test_expired_and_recalculate(client, headers, make_extinguisher, base_refs):
    ext = make_extinguisher(inventory_number="ОП-777", type="ОП-4", capacity=4)
    today = date.today()
    client.post("/inspections/", headers=headers, json={
        "fire_extinguisher_id": ext["id"], "employee_id": base_refs["employee_id"],
        "inspection_date": (today - timedelta(days=200)).isoformat(),
        "next_inspection_date": (today - timedelta(days=5)).isoformat(),
    })
    expired = client.get("/reports/expired", headers=headers).json()
    item = next(e for e in expired if e["inventory_number"] == "ОП-777")
    assert item["days_overdue"] == 5


def test_import_reports_bad_rows(client, headers, base_refs):
    loc = base_refs["location"]
    csv_text = (
        "inventory_number;type;capacity;manufacturer;manufacture_date;commissioning_date;location_name;status_name;last_recharge_date;recharge_interval_months\n"
        f"ИМП-1;ОУ-2;2;;2023-01-01;;{loc};Актуально;2024-01-01;60\n"
        f"ИМП-1;ОУ-2;2;;2023-01-01;;{loc};Актуально;;\n"
        f"ИМП-2;ОУ-2;2;;01/01/2023;;{loc};Актуально;;\n"
        f"ИМП-3;ОУ-2;abc;;;;{loc};;;\n"
        f"ИМП-4;ОУ-2;2;;;;{loc};;;999\n"
    )
    resp = client.post("/import/extinguishers", headers=headers,
                       files={"file": ("import.csv", csv_text.encode("cp1251"), "text/csv")})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] == 1
    assert len(body["errors"]) == 4

    imported = next(e for e in client.get("/extinguishers/", headers=headers).json()
                    if e["inventory_number"] == "ИМП-1")
    assert imported["last_recharge_date"] == "2024-01-01"
    assert imported["next_recharge_date"] == "2029-01-01"


def test_import_missing_columns(client, headers):
    resp = client.post("/import/locations", headers=headers,
                       files={"file": ("import.csv", "title;x\nA;B\n".encode(), "text/csv")})
    assert resp.status_code == 400


def test_import_template_has_recharge_columns(client, headers):
    resp = client.get("/import/templates/extinguishers", headers=headers)
    assert resp.status_code == 200
    assert "last_recharge_date" in resp.text.splitlines()[0]
