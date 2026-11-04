# tests/test_audit.py
"""Тесты журнала действий."""
import json

from conftest import USER_PASSWORD


def _entries(client, headers, **params):
    resp = client.get("/audit/", headers=headers, params={"page_size": 200, **params})
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


def test_create_update_delete_logged(client, headers, make_extinguisher):
    ext = make_extinguisher(manufacturer="Старый")
    eid = ext["id"]
    client.put(f"/extinguishers/{eid}", headers=headers, json={"manufacturer": "Новый", "capacity": 6})
    client.delete(f"/extinguishers/{eid}", headers=headers)

    items = _entries(client, headers, entity_type="extinguisher", entity_id=eid)
    actions = [i["action"] for i in items]
    assert actions == ["delete", "update", "create"]  # новые сверху

    update = items[1]
    assert update["username"] == "admin"
    assert update["changes"]["manufacturer"] == {"old": "Старый", "new": "Новый"}
    assert update["changes"]["capacity"] == {"old": 5.0, "new": 6.0}
    assert "inventory_number" not in update["changes"]  # только изменившиеся поля
    assert update["ip"]
    assert ext["inventory_number"] in items[0]["summary"]


def test_noop_update_not_logged(client, headers, make_extinguisher):
    ext = make_extinguisher()
    client.put(f"/extinguishers/{ext['id']}", headers=headers, json={"type": ext["type"]})
    # SQLite может выдать id удаленного огнетушителя повторно, поэтому ищем по номеру
    items = _entries(client, headers, entity_type="extinguisher", q=ext["inventory_number"])
    assert [i["action"] for i in items] == ["create"]


def test_login_events_logged_without_passwords(client, headers, make_user):
    user, _ = make_user("viewer")
    client.post("/auth/token", data={"username": "ghost_user", "password": "Secret-Guess-1"})

    failed = _entries(client, headers, action="login_failed", username="ghost_user")
    assert failed and "ghost_user" in failed[0]["summary"]
    ok = _entries(client, headers, action="login_success", username=user["username"])
    assert ok

    # Ни пароли, ни хеши не попадают в журнал
    dump = json.dumps(_entries(client, headers), ensure_ascii=False)
    assert "Secret-Guess-1" not in dump
    assert USER_PASSWORD not in dump
    assert "pbkdf2" not in dump


def test_user_admin_actions_logged(client, headers, make_user):
    user, _ = make_user("engineer")
    client.post(f"/users/{user['id']}/status", headers=headers, json={"is_active": False})
    client.post(f"/users/{user['id']}/status", headers=headers, json={"is_active": True})
    client.post(f"/users/{user['id']}/reset-password", headers=headers,
                json={"new_password": "Reset-Pass-55"})
    items = _entries(client, headers, entity_type="user", entity_id=user["id"])
    actions = [i["action"] for i in items]
    for expected in ("create", "block", "unblock", "password_reset"):
        assert expected in actions
    assert "Reset-Pass-55" not in json.dumps(items, ensure_ascii=False)


def test_import_logged(client, headers):
    client.post("/import/locations", headers=headers,
                files={"file": ("l.csv", "name;description\nАудит-место;\nАудит-место;\n".encode(),
                                "text/csv")})
    item = _entries(client, headers, action="import", entity_type="location")[0]
    assert item["changes"]["created"]["new"] == 1
    assert item["changes"]["errors"]["new"] == 1


def test_filters_pagination_and_csv(client, headers):
    page = client.get("/audit/", headers=headers, params={"page_size": 2, "page": 1}).json()
    assert page["total"] >= 2 and len(page["items"]) == 2
    meta = client.get("/audit/meta", headers=headers).json()
    assert "admin" in meta["usernames"]
    assert any(a["key"] == "login_failed" for a in meta["actions"])

    csv = client.get("/audit/export.csv", headers=headers, params={"action": "login_success"})
    assert csv.status_code == 200
    assert csv.headers["content-type"].startswith("text/csv")
    lines = csv.text.lstrip("﻿").splitlines()
    assert lines[0].startswith("ID;Время (UTC)")
    assert len(lines) > 1
    assert _entries(client, headers, action="export", entity_type="audit")
