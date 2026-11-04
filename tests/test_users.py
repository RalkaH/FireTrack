# tests/test_users.py
"""Тесты админки пользователей, смены пароля и защиты сессий."""
from datetime import datetime, timezone

import pytest

import auth
from conftest import ADMIN_PASSWORD, USER_PASSWORD, login


@pytest.mark.parametrize("role", ["engineer", "viewer"])
def test_only_admin_manages_users(client, make_user, role):
    user, h = make_user(role)
    assert client.get("/users/", headers=h).status_code == 403
    assert client.post("/users/", headers=h, json={
        "username": "hacker", "full_name": "X", "email": "x@example.com",
        "role": "admin", "password": "Whatever-123"}).status_code == 403
    assert client.post(f"/users/{user['id']}/status", headers=h,
                       json={"is_active": False}).status_code == 403
    assert client.get("/audit/", headers=h).status_code == 403
    assert client.put("/settings/", headers=h, json={"service_life_years": 5}).status_code == 403


def test_engineer_can_edit_viewer_cannot(client, make_user):
    _, eh = make_user("engineer")
    _, vh = make_user("viewer")
    assert client.post("/employees/", headers=eh,
                       json={"full_name": "Инженерный", "position": "Мастер"}).status_code == 201
    assert client.post("/employees/", headers=vh,
                       json={"full_name": "Наблюдатель", "position": "Мастер"}).status_code == 403


def test_create_user_validation(client, headers, make_user):
    base = {"username": "new_user", "full_name": "Новый", "email": "new@example.com", "role": "viewer"}
    assert client.post("/users/", headers=headers, json={**base, "password": "short"}).status_code == 422
    assert client.post("/users/", headers=headers, json={**base, "password": "admin123"}).status_code == 422
    assert client.post("/users/", headers=headers,
                       json={**base, "password": "Good-Pass-1", "role": "root"}).status_code == 422
    assert client.post("/users/", headers=headers,
                       json={**base, "username": "плохой логин", "password": "Good-Pass-1"}).status_code == 422

    user, _ = make_user("viewer")
    dup = client.post("/users/", headers=headers, json={**base, "username": user["username"].upper(),
                                                        "password": "Good-Pass-1"})
    assert dup.status_code == 400
    dup_email = client.post("/users/", headers=headers, json={**base, "email": user["email"],
                                                              "password": "Good-Pass-1"})
    assert dup_email.status_code == 400


def test_last_admin_protection(client, headers):
    me = client.get("/auth/me", headers=headers).json()
    resp = client.post(f"/users/{me['id']}/status", headers=headers, json={"is_active": False})
    assert resp.status_code == 400
    resp = client.put(f"/users/{me['id']}", headers=headers, json={"role": "viewer"})
    assert resp.status_code == 400
    assert client.get("/auth/me", headers=headers).json()["role"] == "admin"


def test_second_admin_can_be_managed(client, headers, make_user):
    # Пока есть другой активный админ, второго можно блокировать и понижать
    other, _ = make_user("admin")
    assert client.post(f"/users/{other['id']}/status", headers=headers,
                       json={"is_active": False}).status_code == 200
    assert client.post(f"/users/{other['id']}/status", headers=headers,
                       json={"is_active": True}).status_code == 200
    assert client.put(f"/users/{other['id']}", headers=headers,
                      json={"role": "engineer"}).status_code == 200


def test_block_revokes_token_and_login(client, headers, make_user):
    user, uh = make_user("engineer")
    assert client.get("/locations/", headers=uh).status_code == 200

    resp = client.post(f"/users/{user['id']}/status", headers=headers, json={"is_active": False})
    assert resp.status_code == 200 and resp.json()["is_active"] is False
    # Старый токен сразу не работает
    assert client.get("/locations/", headers=uh).status_code == 401
    # Войти нельзя
    resp = client.post("/auth/token", data={"username": user["username"], "password": USER_PASSWORD})
    assert resp.status_code == 403

    client.post(f"/users/{user['id']}/status", headers=headers, json={"is_active": True})
    login(client, user["username"], USER_PASSWORD)


def test_role_change_revokes_token(client, headers, make_user):
    user, uh = make_user("engineer")
    client.put(f"/users/{user['id']}", headers=headers, json={"role": "viewer"})
    assert client.get("/locations/", headers=uh).status_code == 401
    vh = login(client, user["username"], USER_PASSWORD)
    assert client.post("/locations/", headers=vh, json={"name": "Нельзя"}).status_code == 403


def test_change_password(client, make_user):
    user, uh = make_user("viewer")
    bad = client.post("/auth/change-password", headers=uh,
                      json={"old_password": "wrong-pass", "new_password": "Another-Pass-9"})
    assert bad.status_code == 400
    weak = client.post("/auth/change-password", headers=uh,
                       json={"old_password": USER_PASSWORD, "new_password": "1234567"})
    assert weak.status_code == 422
    same = client.post("/auth/change-password", headers=uh,
                       json={"old_password": USER_PASSWORD, "new_password": USER_PASSWORD})
    assert same.status_code == 422

    ok = client.post("/auth/change-password", headers=uh,
                     json={"old_password": USER_PASSWORD, "new_password": "Another-Pass-9"})
    assert ok.status_code == 200, ok.text
    new_headers = {"Authorization": f"Bearer {ok.json()['access_token']}"}
    # Старый токен отозван, новый работает
    assert client.get("/auth/me", headers=uh).status_code == 401
    assert client.get("/auth/me", headers=new_headers).status_code == 200
    # Вход только с новым паролем
    assert client.post("/auth/token", data={"username": user["username"],
                                            "password": USER_PASSWORD}).status_code == 401
    login(client, user["username"], "Another-Pass-9")


def test_reset_password_forces_change(client, headers, make_user):
    user, uh = make_user("engineer")
    resp = client.post(f"/users/{user['id']}/reset-password", headers=headers,
                       json={"new_password": "Temp-Pass-123"})
    assert resp.status_code == 200 and resp.json()["must_change_password"] is True
    assert client.get("/locations/", headers=uh).status_code == 401

    token = client.post("/auth/token", data={"username": user["username"], "password": "Temp-Pass-123"})
    assert token.status_code == 200 and token.json()["must_change_password"] is True
    th = {"Authorization": f"Bearer {token.json()['access_token']}"}

    # Пока пароль не сменен, работают только /auth/me и смена пароля
    blocked = client.get("/locations/", headers=th)
    assert blocked.status_code == 403
    assert blocked.headers.get(auth.PASSWORD_CHANGE_HEADER) == "1"
    assert client.get("/auth/me", headers=th).json()["must_change_password"] is True

    changed = client.post("/auth/change-password", headers=th,
                          json={"old_password": "Temp-Pass-123", "new_password": "My-Own-Pass-7"})
    assert changed.status_code == 200
    nh = {"Authorization": f"Bearer {changed.json()['access_token']}"}
    assert client.get("/locations/", headers=nh).status_code == 200


def test_login_throttle(client):
    for _ in range(auth.LOGIN_MAX_FAILURES):
        resp = client.post("/auth/token", data={"username": "brute", "password": "nope"})
        assert resp.status_code == 401
    locked = client.post("/auth/token", data={"username": "brute", "password": "nope"})
    assert locked.status_code == 429
    assert int(locked.headers["Retry-After"]) > 0
    # Другой логин с того же IP не заблокирован
    assert client.post("/auth/token", data={"username": "admin",
                                            "password": ADMIN_PASSWORD}).status_code == 200


def test_default_admin_password_flagged(client):
    """Админ со старым паролем admin123 (база с прошлых версий) обязан его сменить."""
    from db import SessionLocal
    from main import init_admin
    from models import User

    db = SessionLocal()
    try:
        db.add(User(username="legacy_admin_check", email="legacy@example.com",
                    hashed_password=auth.get_password_hash(auth.DEFAULT_ADMIN_PASSWORD),
                    full_name="Legacy", role="admin", is_active=1,
                    created_at=datetime.now(timezone.utc)))
        admin = db.query(User).filter(User.username == "admin").first()
        original_hash = admin.hashed_password
        admin.hashed_password = auth.get_password_hash(auth.DEFAULT_ADMIN_PASSWORD)
        db.commit()

        init_admin()
        db.expire_all()
        admin = db.query(User).filter(User.username == "admin").first()
        assert admin.must_change_password is True

        # Возвращаем как было, чтобы не мешать другим тестам
        admin.hashed_password = original_hash
        admin.must_change_password = False
        db.commit()
    finally:
        db.close()
