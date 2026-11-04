# tests/test_migrations.py
"""Тесты миграций: старая база без alembic_version, новая база, резервная копия."""
import sqlite3

from sqlalchemy import create_engine, inspect

import migrate

# Схема V3, как ее создавал create_all (взята из рабочей базы)
LEGACY_SCHEMA = """
CREATE TABLE "Locations" (id INTEGER NOT NULL, name VARCHAR NOT NULL, description VARCHAR,
    created_at DATETIME NOT NULL, PRIMARY KEY (id), UNIQUE (name));
CREATE TABLE "Statuses" (id INTEGER NOT NULL, name VARCHAR NOT NULL, description VARCHAR NOT NULL,
    created_at DATETIME NOT NULL, PRIMARY KEY (id), UNIQUE (name));
CREATE TABLE "Employees" (id INTEGER NOT NULL, full_name VARCHAR NOT NULL, position VARCHAR NOT NULL,
    created_at DATETIME NOT NULL, PRIMARY KEY (id));
CREATE TABLE "Users" (id INTEGER NOT NULL, username VARCHAR NOT NULL, email VARCHAR NOT NULL,
    hashed_password VARCHAR NOT NULL, full_name VARCHAR NOT NULL, role VARCHAR NOT NULL,
    is_active INTEGER, created_at DATETIME NOT NULL, PRIMARY KEY (id), UNIQUE (email));
CREATE UNIQUE INDEX "ix_Users_username" ON "Users" (username);
CREATE TABLE "FireExtinguishers" (id INTEGER NOT NULL, inventory_number VARCHAR NOT NULL,
    type VARCHAR NOT NULL, capacity FLOAT NOT NULL, manufacturer VARCHAR, manufacture_date DATE,
    commissioning_date DATE, location_id INTEGER NOT NULL, status_id INTEGER NOT NULL,
    created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, PRIMARY KEY (id),
    UNIQUE (inventory_number), FOREIGN KEY(location_id) REFERENCES "Locations" (id),
    FOREIGN KEY(status_id) REFERENCES "Statuses" (id));
CREATE TABLE "Inspections" (id INTEGER NOT NULL, fire_extinguisher_id INTEGER NOT NULL,
    inspection_date DATE NOT NULL, employee_id INTEGER NOT NULL, pressure FLOAT, weight FLOAT,
    visual_inspection VARCHAR, seal_condition VARCHAR, safety_pin_condition VARCHAR,
    hose_condition VARCHAR, comments VARCHAR, next_inspection_date DATE NOT NULL,
    created_at DATETIME NOT NULL, PRIMARY KEY (id),
    FOREIGN KEY(fire_extinguisher_id) REFERENCES "FireExtinguishers" (id),
    FOREIGN KEY(employee_id) REFERENCES "Employees" (id));
INSERT INTO "Locations" VALUES (1, 'Цех', NULL, '2026-05-01 10:00:00');
INSERT INTO "Statuses" VALUES (1, 'Актуально', 'ok', '2026-05-01 10:00:00');
INSERT INTO "FireExtinguishers" VALUES (1, 'ОП-1', 'ОП-5', 5, NULL, '2024-01-01', NULL, 1, 1,
    '2026-05-01 10:00:00', '2026-05-01 10:00:00');
INSERT INTO "Users" VALUES (1, 'admin', 'a@example.com', 'x', 'Admin', 'admin', 1, '2026-05-01 10:00:00');
"""


def _columns(engine, table):
    return {c["name"] for c in inspect(engine).get_columns(table)}


def test_legacy_database_is_stamped_and_upgraded(tmp_path, monkeypatch):
    monkeypatch.setattr(migrate, "BACKUP_DIR", tmp_path / "backups")
    db_file = tmp_path / "legacy.db"
    con = sqlite3.connect(db_file)
    con.executescript(LEGACY_SCHEMA)
    con.close()

    engine = create_engine(f"sqlite:///{db_file}")
    head = migrate.upgrade_database(engine)
    assert head == "0004_recharge_and_settings"

    assert {"must_change_password", "token_version", "last_login_at"} <= _columns(engine, "Users")
    assert {"last_recharge_date", "recharge_interval_months"} <= _columns(engine, "FireExtinguishers")
    assert "AuditLog" in inspect(engine).get_table_names()

    con = sqlite3.connect(db_file)
    assert con.execute('SELECT inventory_number FROM "FireExtinguishers"').fetchall() == [("ОП-1",)]
    assert con.execute('SELECT must_change_password, token_version FROM "Users"').fetchall() == [(0, 0)]
    con.close()

    backups = list((tmp_path / "backups").glob("legacy_*_before_*.db"))
    assert len(backups) == 1

    # Повторный запуск ничего не делает и новую копию не создает
    assert migrate.upgrade_database(engine) == head
    assert len(list((tmp_path / "backups").glob("*.db"))) == 1
    engine.dispose()


def test_fresh_database_created_by_migrations(tmp_path, monkeypatch):
    monkeypatch.setattr(migrate, "BACKUP_DIR", tmp_path / "backups")
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    migrate.upgrade_database(engine)
    tables = set(inspect(engine).get_table_names())
    assert {"Users", "FireExtinguishers", "AuditLog", "Settings", "alembic_version"} <= tables
    assert not (tmp_path / "backups").exists()  # копировать было нечего
    engine.dispose()
