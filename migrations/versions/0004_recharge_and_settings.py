"""перезарядка и срок службы огнетушителей, таблица настроек

Revision ID: 0004_recharge_and_settings
Revises: 0003_audit_log
Create Date: 2026-11-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_recharge_and_settings"
down_revision: Union[str, Sequence[str], None] = "0003_audit_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет сроки в FireExtinguishers и создает Settings."""
    with op.batch_alter_table("FireExtinguishers") as batch:
        batch.add_column(sa.Column("last_recharge_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("recharge_interval_months", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("service_life_years", sa.Integer(), nullable=True))

    op.create_table(
        "Settings",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    """Удаляет Settings и колонки сроков."""
    op.drop_table("Settings")
    with op.batch_alter_table("FireExtinguishers") as batch:
        batch.drop_column("service_life_years")
        batch.drop_column("recharge_interval_months")
        batch.drop_column("last_recharge_date")
