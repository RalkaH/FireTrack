"""users: обязательная смена пароля, версия токена, последний вход

Revision ID: 0002_users_security
Revises: 0001_baseline
Create Date: 2026-11-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_users_security"
down_revision: Union[str, Sequence[str], None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет колонки безопасности в Users."""
    with op.batch_alter_table("Users") as batch:
        batch.add_column(sa.Column(
            "must_change_password", sa.Boolean(), nullable=False,
            server_default=sa.text("0")))
        batch.add_column(sa.Column(
            "token_version", sa.Integer(), nullable=False,
            server_default=sa.text("0")))
        batch.add_column(sa.Column("last_login_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Удаляет колонки безопасности."""
    with op.batch_alter_table("Users") as batch:
        batch.drop_column("last_login_at")
        batch.drop_column("token_version")
        batch.drop_column("must_change_password")
