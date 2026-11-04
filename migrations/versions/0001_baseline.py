"""baseline: схема на момент V3

Описывает таблицы в том виде, в каком их создавал ``create_all`` до
появления миграций. Базы, созданные до V4, помечаются этой ревизией
автоматически (``alembic stamp``), и для них она не выполняется.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создает исходные таблицы."""
    op.create_table(
        "Locations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_Locations_id", "Locations", ["id"])

    op.create_table(
        "Statuses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_Statuses_id", "Statuses", ["id"])

    op.create_table(
        "Employees",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("position", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_Employees_id", "Employees", ["id"])

    op.create_table(
        "Users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("is_active", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_Users_username", "Users", ["username"], unique=True)
    op.create_index("ix_Users_id", "Users", ["id"])

    op.create_table(
        "FireExtinguishers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inventory_number", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("capacity", sa.Float(), nullable=False),
        sa.Column("manufacturer", sa.String(), nullable=True),
        sa.Column("manufacture_date", sa.Date(), nullable=True),
        sa.Column("commissioning_date", sa.Date(), nullable=True),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("status_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["Locations.id"]),
        sa.ForeignKeyConstraint(["status_id"], ["Statuses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inventory_number"),
    )
    op.create_index("ix_FireExtinguishers_id", "FireExtinguishers", ["id"])

    op.create_table(
        "Inspections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fire_extinguisher_id", sa.Integer(), nullable=False),
        sa.Column("inspection_date", sa.Date(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("pressure", sa.Float(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("visual_inspection", sa.String(), nullable=True),
        sa.Column("seal_condition", sa.String(), nullable=True),
        sa.Column("safety_pin_condition", sa.String(), nullable=True),
        sa.Column("hose_condition", sa.String(), nullable=True),
        sa.Column("comments", sa.String(), nullable=True),
        sa.Column("next_inspection_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["Employees.id"]),
        sa.ForeignKeyConstraint(["fire_extinguisher_id"], ["FireExtinguishers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_Inspections_id", "Inspections", ["id"])


def downgrade() -> None:
    """Удаляет все таблицы (данные будут потеряны)."""
    for table in ("Inspections", "FireExtinguishers", "Users",
                  "Employees", "Statuses", "Locations"):
        op.drop_table(table)
