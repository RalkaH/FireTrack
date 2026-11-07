# tests/test_platform.py
"""Тесты резервных копий, заголовков безопасности, работы без интернета и защиты выгрузок."""
import re
import sqlite3
from datetime import datetime, timedelta
from io import BytesIO
from os import utime
from pathlib import Path

import pytest
from openpyxl import load_workbook

import auth
import backup
import migrate
from conftest import USER_PASSWORD
from export_utils import safe_cell
from main import CONTENT_SECURITY_POLICY

STATIC = Path(__file__).resolve().parents[1] / "static"


# ---------- Резервные копии ----------

def test_backup_create_list_download(client, headers):
    created = client.post("/backups/", headers=headers)
    assert created.status_code == 201, created.text
    name = created.json()["name"]
    assert "_manual_" in name

    items = client.get("/backups/", headers=headers).json()
    entry = next(b for b in items if b["name"] == name)
    assert entry["kind"] == "manual" and entry["size"] > 0
    assert entry["created_at"].endswith("Z")

    resp = client.get(f"/backups/{name}", headers=headers)
    assert resp.status_code == 200
    assert resp.content.startswith(b"SQLite format 3")

    actions = client.get("/audit/", headers=headers, params={"action": "backup"}).json()["items"]
    assert any("Создана" in a["summary"] and name in a["summary"] for a in actions)
    assert any("Скачана" in a["summary"] and name in a["summary"] for a in actions)


def test_backup_is_a_working_database(client, headers, tmp_path):
    name = client.post("/backups/", headers=headers).json()["name"]
    target = tmp_path / "restored.db"
    target.write_bytes(client.get(f"/backups/{name}", headers=headers).content)
    con = sqlite3.connect(target)
    assert con.execute('SELECT COUNT(*) FROM "Users"').fetchone()[0] >= 1
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    con.close()


@pytest.mark.parametrize("name", ["..%2F..%2Fmain.py", "..%5C..%5Cmain.py", "nope.db", "..%2Ftest.db", "a.txt"])
def test_backup_download_rejects_bad_names(client, headers, name):
    assert client.get(f"/backups/{name}", headers=headers).status_code == 404


def test_backups_admin_only(client, make_user):
    _, eh = make_user("engineer")
    assert client.get("/backups/", headers=eh).status_code == 403
    assert client.post("/backups/", headers=eh).status_code == 403
    assert client.get("/backups/x.db", headers=eh).status_code == 403
    assert client.get("/backups/").status_code == 401


def test_scheduled_backup_once_a_day_and_prune(tmp_path, monkeypatch):
    monkeypatch.setattr(migrate, "BACKUP_DIR", tmp_path)
    assert backup.run_scheduled_backup(keep=3) is not None
    assert backup.run_scheduled_backup(keep=3) is None  # сутки не прошли

    # Старим копию на двое суток: теперь новая нужна
    first = next(tmp_path.glob("*_auto_*.db"))
    old = (datetime.now() - timedelta(days=2)).timestamp()
    utime(first, (old, old))
    assert backup.run_scheduled_backup(keep=3) is not None

    # Лишние автокопии удаляются, начиная со старых; ручные не трогаем
    manual = tmp_path / "base_manual_1.db"
    manual.write_bytes(b"x")
    for i in range(5):
        path = tmp_path / f"base_auto_{i}.db"
        path.write_bytes(b"x")
        stamp = (datetime.now() - timedelta(days=10 + i)).timestamp()
        utime(path, (stamp, stamp))
    assert backup.prune_auto_backups(keep=2) > 0
    assert len(list(tmp_path.glob("*_auto_*.db"))) == 2
    assert manual.exists()
    assert not (tmp_path / "base_auto_4.db").exists()


def test_backup_keep_setting_validated(client, headers):
    assert client.put("/settings/", headers=headers, json={"backup_keep_count": 0}).status_code == 422
    assert client.put("/settings/", headers=headers, json={"backup_keep_count": 30}).status_code == 200
    client.put("/settings/", headers=headers, json={"backup_keep_count": 14})


# ---------- Заголовки и работа без интернета ----------

def test_security_headers(client, headers):
    resp = client.get("/auth/me", headers=headers)
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Cache-Control"] == "no-store"
    assert resp.headers["Content-Security-Policy"] == CONTENT_SECURITY_POLICY
    assert "http" not in CONTENT_SECURITY_POLICY

    page = client.get("/")
    assert page.status_code == 200
    assert "Content-Security-Policy" in page.headers
    # Swagger грузится с CDN, для него политика не применяется
    assert "Content-Security-Policy" not in client.get("/docs").headers
    # Статика кэшируется браузером
    assert "Cache-Control" not in client.get("/static/js/api.js").headers


def test_frontend_has_no_external_resources():
    """Интерфейс не должен ничего загружать из интернета."""
    pattern = re.compile(r"""(?:src|href)=["']https?://|url\(["']?https?://|@import url\(["']?https?://""")
    files = list(STATIC.glob("*.html")) + list((STATIC / "js").glob("*.js")) + list((STATIC / "css").glob("*.css"))
    assert files
    for path in files:
        assert not pattern.search(path.read_text(encoding="utf-8")), path.name


def test_vendor_files_served(client):
    for path in ("vendor/bootstrap/bootstrap.min.css", "vendor/bootstrap/bootstrap.bundle.min.js",
                 "vendor/bootstrap-icons/bootstrap-icons.min.css",
                 "vendor/bootstrap-icons/fonts/bootstrap-icons.woff2",
                 "vendor/inter/inter.css", "vendor/inter/inter-cyrillic.woff2", "favicon.ico"):
        assert client.get(f"/static/{path}").status_code == 200, path
    assert client.get("/favicon.ico").status_code == 200


# ---------- Защита выгрузок ----------

@pytest.mark.parametrize("value, expected", [
    ("=cmd|' /C calc'!A0", "'=cmd|' /C calc'!A0"), ("+1", "'+1"), ("-1", "'-1"), ("@x", "'@x"),
    ("\tx", "'\tx"), ("ОП-5", "ОП-5"), (5.5, 5.5), (None, None), ("", ""),
])
def test_safe_cell(value, expected):
    assert safe_cell(value) == expected


def test_formula_injection_neutralized_in_audit_csv(client, headers):
    client.post("/auth/token", data={"username": "=HYPERLINK(evil)", "password": "whatever-1"})
    text = client.get("/audit/export.csv", headers=headers, params={"action": "login_failed"}).text
    for line in text.lstrip("﻿").splitlines()[1:]:
        for cell in line.split(";"):
            assert not cell.startswith("="), line


def test_formula_injection_neutralized_in_xlsx(client, headers, make_extinguisher, base_refs):
    ext = make_extinguisher(inventory_number=f"=SUM(A1)+{base_refs['employee_id']}")
    client.post("/inspections/", headers=headers, json={
        "fire_extinguisher_id": ext["id"], "employee_id": base_refs["employee_id"],
        "inspection_date": datetime.now().date().isoformat()})
    ws = load_workbook(BytesIO(client.get("/reports/journal.xlsx", headers=headers).content)).active
    cells = [c for row in ws.iter_rows() for c in row if isinstance(c.value, str) and "SUM(A1)" in c.value]
    assert cells
    assert all(c.data_type == "s" and c.value.startswith("'") for c in cells)
    client.delete(f"/extinguishers/{ext['id']}", headers=headers)


# ---------- Мелкие защиты ----------

def test_password_too_long_rejected(client, make_user):
    _, uh = make_user("viewer")
    resp = client.post("/auth/change-password", headers=uh,
                       json={"old_password": USER_PASSWORD, "new_password": "x1" * 3000})
    assert resp.status_code == 422


def test_long_login_is_truncated(client, headers):
    resp = client.post("/auth/token", data={"username": "L" * 5000, "password": "whatever-1"})
    assert resp.status_code == 401
    items = client.get("/audit/", headers=headers, params={"action": "login_failed"}).json()["items"]
    assert all(len(i["username"] or "") <= 150 for i in items)


def test_throttle_does_not_keep_unknown_logins(client):
    auth.login_throttle.reset()
    for i in range(20):
        auth.login_throttle.retry_after(f"user{i}", "1.2.3.4")
    assert auth.login_throttle._failures == {}


def test_password_fields_have_show_button():
    """На входе и в смене пароля есть кнопка показа пароля."""
    assert "data-toggle-password" in (STATIC / "login.html").read_text(encoding="utf-8")
    account = (STATIC / "js" / "account.js").read_text(encoding="utf-8")
    assert account.count("passwordToggle()") == 3
