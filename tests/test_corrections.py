# tests/test_corrections.py
"""Тесты исправления ошибок: места, сотрудники, проверки, записи о ТО."""
from datetime import date, timedelta
from uuid import uuid4

from conftest import status_id
from deadlines import add_months


def _entries(client, headers, **params):
    return client.get("/audit/", headers=headers, params={"page_size": 200, **params}).json()["items"]


def _location(client, headers):
    resp = client.post("/locations/", headers=headers, json={"name": f"Место {uuid4().hex[:8]}"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _employee(client, headers):
    resp = client.post("/employees/", headers=headers,
                       json={"full_name": f"Сотрудник {uuid4().hex[:8]}", "position": "Мастер"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _inspection(client, headers, ext_id, emp_id, **fields):
    today = date.today()
    data = {"fire_extinguisher_id": ext_id, "employee_id": emp_id,
            "inspection_date": today.isoformat(),
            "next_inspection_date": (today + timedelta(days=100)).isoformat()}
    data.update(fields)
    resp = client.post("/inspections/", headers=headers, json=data)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------- Места ----------

def test_location_edit_and_delete(client, headers, make_extinguisher):
    other = _location(client, headers)
    loc = _location(client, headers)

    resp = client.put(f"/locations/{loc['id']}", headers=headers,
                      json={"name": "  Новое " + loc["name"] + " ", "description": "Этаж 2"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Новое " + loc["name"]
    assert client.put(f"/locations/{loc['id']}", headers=headers,
                      json={"name": other["name"]}).status_code == 400

    entry = _entries(client, headers, entity_type="location", entity_id=loc["id"], action="update")[0]
    assert entry["changes"]["description"] == {"old": None, "new": "Этаж 2"}

    # Место с огнетушителем удалить нельзя
    ext = make_extinguisher(location_id=loc["id"])
    resp = client.delete(f"/locations/{loc['id']}", headers=headers)
    assert resp.status_code == 409
    client.delete(f"/extinguishers/{ext['id']}", headers=headers)
    assert client.delete(f"/locations/{loc['id']}", headers=headers).status_code == 204
    assert client.put(f"/locations/{loc['id']}", headers=headers, json={"name": "X"}).status_code == 404


def test_location_permissions(client, headers, make_user):
    loc = _location(client, headers)
    _, eh = make_user("engineer")
    _, vh = make_user("viewer")
    assert client.put(f"/locations/{loc['id']}", headers=vh, json={"description": "x"}).status_code == 403
    assert client.put(f"/locations/{loc['id']}", headers=eh, json={"description": "x"}).status_code == 200
    assert client.delete(f"/locations/{loc['id']}", headers=eh).status_code == 403


# ---------- Сотрудники ----------

def test_employee_edit_and_delete(client, headers, make_extinguisher):
    emp = _employee(client, headers)
    resp = client.put(f"/employees/{emp['id']}", headers=headers, json={"position": "  Инженер "})
    assert resp.status_code == 200 and resp.json()["position"] == "Инженер"
    assert client.put(f"/employees/{emp['id']}", headers=headers, json={"full_name": "   "}).status_code == 400

    # Сотрудника с проверками удалить нельзя, даже если проверка аннулирована
    ext = make_extinguisher()
    insp = _inspection(client, headers, ext["id"], emp["id"])
    assert client.delete(f"/employees/{emp['id']}", headers=headers).status_code == 409
    client.post(f"/inspections/{insp['id']}/annul", headers=headers, json={"reason": "Ошибка ввода"})
    assert client.delete(f"/employees/{emp['id']}", headers=headers).status_code == 409

    free = _employee(client, headers)
    assert client.delete(f"/employees/{free['id']}", headers=headers).status_code == 204


# ---------- Проверки ----------

def test_inspection_correction_recalculates_status(client, headers, base_refs, make_extinguisher):
    ext = make_extinguisher(type="Кошма")
    insp = _inspection(client, headers, ext["id"], base_refs["employee_id"], seal_condition="Отсутствует")
    needs = status_id(client, headers, "Требует обслуживания")
    assert client.get(f"/extinguishers/{ext['id']}", headers=headers).json()["status_id"] == needs

    # Без причины нельзя
    assert client.put(f"/inspections/{insp['id']}", headers=headers,
                      json={"seal_condition": "Цела"}).status_code == 422

    resp = client.put(f"/inspections/{insp['id']}", headers=headers,
                      json={"seal_condition": "Цела", "reason": "Опечатка при вводе"})
    assert resp.status_code == 200, resp.text
    assert client.get(f"/extinguishers/{ext['id']}", headers=headers).json()["status_id"] == \
        status_id(client, headers, "Актуально")

    entry = _entries(client, headers, entity_type="inspection", entity_id=insp["id"], action="update")[0]
    assert "Опечатка при вводе" in entry["summary"]
    assert entry["changes"]["seal_condition"] == {"old": "Отсутствует", "new": "Цела"}


def test_inspection_correction_validation(client, headers, base_refs, make_extinguisher):
    ext = make_extinguisher()
    insp = _inspection(client, headers, ext["id"], base_refs["employee_id"])
    today = date.today()
    url = f"/inspections/{insp['id']}"
    reason = {"reason": "Исправление"}
    assert client.put(url, headers=headers, json={
        **reason, "next_inspection_date": (today - timedelta(days=1)).isoformat()}).status_code == 400
    assert client.put(url, headers=headers, json={
        **reason, "inspection_date": (today + timedelta(days=1)).isoformat()}).status_code == 422
    assert client.put(url, headers=headers, json={**reason, "employee_id": 999999}).status_code == 400
    assert client.put(url, headers=headers, json={**reason, "next_inspection_date": None}).status_code == 400


def test_annul_excludes_from_status_and_reports(client, headers, base_refs, make_extinguisher):
    today = date.today()
    ext = make_extinguisher(type="Кошма")
    _inspection(client, headers, ext["id"], base_refs["employee_id"],
                inspection_date=(today - timedelta(days=30)).isoformat(),
                next_inspection_date=(today + timedelta(days=100)).isoformat())
    wrong = _inspection(client, headers, ext["id"], base_refs["employee_id"],
                        hose_condition="Отсутствует", comments="ОШИБОЧНАЯ")
    needs = status_id(client, headers, "Требует обслуживания")
    actual = status_id(client, headers, "Актуально")
    assert client.get(f"/extinguishers/{ext['id']}", headers=headers).json()["status_id"] == needs

    assert client.post(f"/inspections/{wrong['id']}/annul", headers=headers,
                       json={"reason": "x"}).status_code == 422
    resp = client.post(f"/inspections/{wrong['id']}/annul", headers=headers,
                       json={"reason": "Ввели не тот огнетушитель"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["annulled_by"] == "admin" and body["annul_reason"] == "Ввели не тот огнетушитель"

    # Статус считается по оставшейся проверке
    assert client.get(f"/extinguishers/{ext['id']}", headers=headers).json()["status_id"] == actual

    # Запись осталась в истории, но не в журналах и отчетах
    history = client.get(f"/inspections/by-extinguisher/{ext['id']}", headers=headers).json()
    assert wrong["id"] in [i["id"] for i in history]
    assert wrong["id"] not in [i["id"] for i in client.get("/inspections/", headers=headers).json()]
    assert wrong["id"] in [i["id"] for i in client.get("/inspections/", headers=headers,
                                                       params={"include_annulled": True}).json()]
    assert wrong["id"] not in [i["id"] for i in client.get("/reports/journal", headers=headers).json()]
    assert "ОШИБОЧНАЯ" not in client.get("/reports/journal.csv", headers=headers).text
    assert "ОШИБОЧНАЯ" not in client.get("/reports/print/journal", headers=headers).text
    assert "ОШИБОЧНАЯ" not in client.get("/reports/print/maintenance", headers=headers).text

    # Аннулированную нельзя исправлять и аннулировать повторно
    assert client.put(f"/inspections/{wrong['id']}", headers=headers,
                      json={"comments": "y", "reason": "Исправление"}).status_code == 400
    assert client.post(f"/inspections/{wrong['id']}/annul", headers=headers,
                       json={"reason": "Повторно"}).status_code == 400

    # Восстановление возвращает все обратно
    assert client.post(f"/inspections/{wrong['id']}/restore", headers=headers,
                       json={"reason": "Ошиблись с аннулированием"}).status_code == 200
    assert client.get(f"/extinguishers/{ext['id']}", headers=headers).json()["status_id"] == needs
    actions = [e["action"] for e in _entries(client, headers, entity_type="inspection", entity_id=wrong["id"])]
    assert "annul" in actions and "restore" in actions


def test_only_admin_corrects_inspections(client, base_refs, headers, make_user, make_extinguisher):
    ext = make_extinguisher()
    insp = _inspection(client, headers, ext["id"], base_refs["employee_id"])
    _, eh = make_user("engineer")
    assert client.put(f"/inspections/{insp['id']}", headers=eh,
                      json={"comments": "x", "reason": "Исправление"}).status_code == 403
    assert client.post(f"/inspections/{insp['id']}/annul", headers=eh,
                       json={"reason": "Причина"}).status_code == 403


# ---------- История ТО ----------

def test_service_records_drive_card_dates(client, headers, make_extinguisher):
    today = date.today()
    old_day = today - timedelta(days=400)
    ext = make_extinguisher(type="ОП-5", manufacture_date=(today - timedelta(days=3000)).isoformat())
    assert ext["last_recharge_date"] is None

    old = client.post("/service-records/", headers=headers, json={
        "fire_extinguisher_id": ext["id"], "service_date": old_day.isoformat(),
        "recharged": True, "tested": True}).json()
    # Сроки посчитаны сервером: порошок и испытания через 5 лет
    assert old["next_recharge_date"] == add_months(old_day, 60).isoformat()
    assert old["next_test_date"] == add_months(old_day, 60).isoformat()

    new = client.post("/service-records/", headers=headers, json={
        "fire_extinguisher_id": ext["id"], "service_date": today.isoformat(), "recharged": True,
        "next_recharge_date": (today + timedelta(days=30)).isoformat()}).json()
    assert new["next_recharge_date"] == (today + timedelta(days=30)).isoformat()  # указан вручную
    assert new["next_test_date"] is None  # испытания не было

    card = client.get(f"/extinguishers/{ext['id']}", headers=headers).json()
    assert card["last_recharge_date"] == today.isoformat()
    assert card["last_test_date"] == old_day.isoformat()
    assert card["next_test_date"] == add_months(old_day, 60).isoformat()

    history = client.get("/service-records/", headers=headers, params={"extinguisher_id": ext["id"]}).json()
    assert [r["id"] for r in history] == [new["id"], old["id"]]

    # Удаление записи возвращает предыдущую дату
    assert client.delete(f"/service-records/{new['id']}", headers=headers,
                         params={"reason": "Ошибочная запись"}).status_code == 204
    card = client.get(f"/extinguishers/{ext['id']}", headers=headers).json()
    assert card["last_recharge_date"] == old_day.isoformat()

    # Исправление даты тоже меняет карточку
    day2 = today - timedelta(days=10)
    resp = client.put(f"/service-records/{old['id']}", headers=headers, json={
        "service_date": day2.isoformat(), "recharged": True, "tested": False, "reason": "Неверная дата"})
    assert resp.status_code == 200, resp.text
    card = client.get(f"/extinguishers/{ext['id']}", headers=headers).json()
    assert card["last_recharge_date"] == day2.isoformat()
    assert card["last_test_date"] is None
    assert resp.json()["next_test_date"] is None


def test_service_record_validation_and_permissions(client, headers, make_user, make_extinguisher):
    ext = make_extinguisher()
    today = date.today().isoformat()
    base = {"fire_extinguisher_id": ext["id"], "service_date": today}
    assert client.post("/service-records/", headers=headers, json=base).status_code == 422  # нет вида работ
    assert client.post("/service-records/", headers=headers, json={
        **base, "recharged": True, "next_recharge_date": "2000-01-01"}).status_code == 422
    assert client.post("/service-records/", headers=headers, json={
        **base, "recharged": True, "fire_extinguisher_id": 999999}).status_code == 400

    _, eh = make_user("engineer")
    _, vh = make_user("viewer")
    assert client.post("/service-records/", headers=vh, json={**base, "repaired": True}).status_code == 403
    created = client.post("/service-records/", headers=eh, json={**base, "repaired": True})
    assert created.status_code == 201
    record_id = created.json()["id"]
    assert client.put(f"/service-records/{record_id}", headers=eh, json={
        "service_date": today, "repaired": True, "reason": "Причина"}).status_code == 403
    assert client.delete(f"/service-records/{record_id}", headers=eh,
                         params={"reason": "Причина"}).status_code == 403
    assert client.delete(f"/service-records/{record_id}", headers=headers).status_code == 422


def test_card_date_cannot_be_set_directly(client, headers, make_extinguisher):
    """Дата перезарядки меняется только через историю, иначе карточка и журнал разойдутся."""
    ext = make_extinguisher()
    client.put(f"/extinguishers/{ext['id']}", headers=headers, json={"last_recharge_date": "2024-01-01"})
    assert client.get(f"/extinguishers/{ext['id']}", headers=headers).json()["last_recharge_date"] is None


def test_initial_recharge_creates_history(client, headers, make_extinguisher):
    day = (date.today() - timedelta(days=100)).isoformat()
    ext = make_extinguisher(last_recharge_date=day, type="ОВ-9")
    history = client.get("/service-records/", headers=headers, params={"extinguisher_id": ext["id"]}).json()
    assert len(history) == 1 and history[0]["service_date"] == day and history[0]["recharged"] is True
    assert ext["last_recharge_date"] == day


def test_delete_extinguisher_removes_history(client, headers, make_extinguisher):
    ext = make_extinguisher(last_recharge_date=date.today().isoformat())
    assert client.delete(f"/extinguishers/{ext['id']}", headers=headers).status_code == 204
    assert client.get("/service-records/", headers=headers,
                      params={"extinguisher_id": ext["id"]}).json() == []
