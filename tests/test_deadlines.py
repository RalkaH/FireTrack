# tests/test_deadlines.py
"""Тесты сроков перезарядки, срока службы и настроек."""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app_settings import DEFAULTS
from conftest import status_id
from deadlines import add_months, agent_kind, compute_deadlines


@pytest.mark.parametrize("type_, kind", [
    ("ОП-5", "powder"), ("оп-4(з)", "powder"), ("OP-5", "powder"),  # латиница
    ("ОУ-3", "co2"), ("ОВП-10", "foam"), ("ОВЭ-6", "water"), ("ОВ-9", "water"),
    ("ОХ-3", "halon"),
])
def test_agent_kind(type_, kind):
    assert agent_kind(type_)["kind"] == kind


def test_agent_kind_unknown():
    assert agent_kind("Кошма") is None
    assert agent_kind(None) is None


def test_add_months_month_end():
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2023, 3, 15), 60) == date(2028, 3, 15)
    assert add_months(date(2024, 12, 1), 12) == date(2025, 12, 1)


def _fe(**kw):
    base = dict(type="ОП-5", manufacture_date=None, commissioning_date=None,
                last_recharge_date=None, recharge_interval_months=None, service_life_years=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_compute_deadlines_defaults():
    today = date(2026, 11, 5)
    d = compute_deadlines(_fe(manufacture_date=date(2021, 12, 1)), DEFAULTS, today)
    assert d["recharge_interval_months"] == 60  # порошок: 1 раз в 5 лет
    assert d["recharge_basis"] == "дата изготовления"
    assert d["next_recharge_date"] == date(2026, 12, 1)
    assert d["recharge_state"] == "soon"
    assert d["service_end_date"] == date(2031, 12, 1)
    assert d["service_state"] == "ok"


def test_compute_deadlines_overrides_and_water():
    today = date(2026, 11, 5)
    d = compute_deadlines(_fe(type="ОВ-9", last_recharge_date=date(2025, 10, 1)), DEFAULTS, today)
    assert d["recharge_interval_months"] == 12  # вода: 1 раз в год
    assert d["recharge_state"] == "overdue"
    d = compute_deadlines(_fe(type="ОВ-9", last_recharge_date=date(2025, 10, 1),
                              recharge_interval_months=36), DEFAULTS, today)
    assert d["recharge_interval_source"] == "карточка"
    assert d["recharge_state"] == "ok"


def test_compute_deadlines_unknown():
    d = compute_deadlines(_fe(type="Кошма"), DEFAULTS, date(2026, 1, 1))
    assert d["recharge_state"] == "unknown"
    assert d["next_recharge_date"] is None


def _with_fresh_inspection(client, headers, base_refs, ext_id):
    today = date.today()
    resp = client.post("/inspections/", headers=headers, json={
        "fire_extinguisher_id": ext_id, "employee_id": base_refs["employee_id"],
        "inspection_date": today.isoformat(),
        "next_inspection_date": (today + timedelta(days=90)).isoformat(),
    })
    assert resp.status_code == 201, resp.text


def test_overdue_recharge_needs_service(client, headers, base_refs, make_extinguisher):
    old = date.today().replace(year=date.today().year - 6)
    ext = make_extinguisher(type="ОП-5", manufacture_date=old.isoformat())
    assert ext["recharge_state"] == "overdue"
    _with_fresh_inspection(client, headers, base_refs, ext["id"])
    fe = client.get(f"/extinguishers/{ext['id']}", headers=headers).json()
    assert fe["status_id"] == status_id(client, headers, "Требует обслуживания")

    # Записываем перезарядку: срок обновляется, статус возвращается в «Актуально»
    resp = client.post("/service-records/", headers=headers, json={
        "fire_extinguisher_id": ext["id"], "service_date": date.today().isoformat(),
        "recharged": True, "comments": "акт №5"})
    assert resp.status_code == 201, resp.text
    body = client.get(f"/extinguishers/{ext['id']}", headers=headers).json()
    assert body["last_recharge_date"] == date.today().isoformat()
    assert body["recharge_state"] == "ok"
    assert body["status_id"] == status_id(client, headers, "Актуально")

    audit = client.get("/audit/", headers=headers,
                       params={"entity_type": "service_record", "entity_id": resp.json()["id"]}).json()
    assert audit["items"][0]["changes"]["comments"]["new"] == "акт №5"


def test_recharge_future_date_rejected(client, headers, make_extinguisher):
    ext = make_extinguisher()
    resp = client.post("/service-records/", headers=headers, json={
        "fire_extinguisher_id": ext["id"], "recharged": True,
        "service_date": (date.today() + timedelta(days=1)).isoformat()})
    assert resp.status_code == 422


def test_setting_disables_recharge_rule(client, headers, base_refs, make_extinguisher):
    old = date.today().replace(year=date.today().year - 6)
    ext = make_extinguisher(type="ОУ-3", manufacture_date=old.isoformat())
    _with_fresh_inspection(client, headers, base_refs, ext["id"])
    needs = status_id(client, headers, "Требует обслуживания")
    assert client.get(f"/extinguishers/{ext['id']}", headers=headers).json()["status_id"] == needs

    resp = client.put("/settings/", headers=headers, json={"recharge_overdue_needs_service": False})
    assert resp.status_code == 200, resp.text
    try:
        fe = client.get(f"/extinguishers/{ext['id']}", headers=headers).json()
        assert fe["status_id"] == status_id(client, headers, "Актуально")
    finally:
        client.put("/settings/", headers=headers, json={"recharge_overdue_needs_service": True})


def test_settings_validation_and_read(client, headers, make_user):
    assert client.put("/settings/", headers=headers, json={"nope": 1}).status_code == 422
    assert client.put("/settings/", headers=headers,
                      json={"recharge_months_powder": 0}).status_code == 422
    assert client.put("/settings/", headers=headers,
                      json={"recharge_months_powder": "abc"}).status_code == 422

    resp = client.put("/settings/", headers=headers, json={"organization_name": "ООО «Тест»"})
    assert resp.status_code == 200
    _, vh = make_user("viewer")
    values = client.get("/settings/", headers=vh).json()["values"]
    assert values["organization_name"] == "ООО «Тест»"
    assert values["recharge_months_powder"] == 60


def test_dashboard_recharge_counts(client, headers, make_extinguisher):
    old = date.today().replace(year=date.today().year - 6)
    make_extinguisher(type="ОП-4", manufacture_date=old.isoformat())
    dash = client.get("/reports/dashboard", headers=headers).json()
    assert dash["recharge_overdue_count"] >= 1
    rows = client.get("/reports/recharge", headers=headers).json()
    assert any(r["state"] == "overdue" for r in rows)
