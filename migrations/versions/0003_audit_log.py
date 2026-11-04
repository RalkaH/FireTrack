"""audit log: журнал действий пользователей

Revision ID: 0003_audit_log
Revises: 0002_users_security
Create Date: 2026-11-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_audit_log"
down_revision: Union[str, Sequence[str], None] = "0002_users_security"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создает таблицу AuditLog."""
    op.create_table(
        "AuditLog",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("changes", sa.Text(), nullable=True),
        sa.Column("ip", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_AuditLog_created_at", "AuditLog", ["created_at"])
    op.create_index("ix_AuditLog_username", "AuditLog", ["username"])
    op.create_index("ix_AuditLog_action", "AuditLog", ["action"])
    op.create_index("ix_AuditLog_entity_type", "AuditLog", ["entity_type"])


def downgrade() -> None:
    """Удаляет таблицу AuditLog."""
    op.drop_table("AuditLog")
