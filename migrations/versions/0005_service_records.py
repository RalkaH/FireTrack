"""история ТО, заводской номер, аннулирование проверок

Добавляет таблицу ServiceRecords (записи о ТО, испытаниях, перезарядке
и ремонте для журнала по форме А.2 ГОСТ Р 59641-2021), заводской номер
и дату последнего испытания огнетушителя (форма А.1), а также поля
аннулирования ошибочных проверок. Уже указанные даты перезарядки
переносятся в историю отдельными записями.

Revision ID: 0005_service_records
Revises: 0004_recharge_and_settings
Create Date: 2026-11-06
"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_service_records"
down_revision: Union[str, Sequence[str], None] = "0004_recharge_and_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создает ServiceRecords и новые колонки, переносит даты перезарядки."""
    with op.batch_alter_table("FireExtinguishers") as batch:
        batch.add_column(sa.Column("serial_number", sa.String(), nullable=True))
        batch.add_column(sa.Column("last_test_date", sa.Date(), nullable=True))

    with op.batch_alter_table("Inspections") as batch:
        batch.add_column(sa.Column("annulled_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("annulled_by", sa.String(), nullable=True))
        batch.add_column(sa.Column("annul_reason", sa.String(), nullable=True))

    op.create_table(
        "ServiceRecords",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fire_extinguisher_id", sa.Integer(), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("tested", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("recharged", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("repaired", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("organization", sa.String(), nullable=True),
        sa.Column("test_result", sa.String(), nullable=True),
        sa.Column("next_test_date", sa.Date(), nullable=True),
        sa.Column("agent_brand", sa.String(), nullable=True),
        sa.Column("post_recharge_result", sa.String(), nullable=True),
        sa.Column("next_recharge_date", sa.Date(), nullable=True),
        sa.Column("responsible", sa.String(), nullable=True),
        sa.Column("comments", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["fire_extinguisher_id"], ["FireExtinguishers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ServiceRecords_fire_extinguisher_id", "ServiceRecords",
                    ["fire_extinguisher_id"])
    op.create_index("ix_ServiceRecords_service_date", "ServiceRecords", ["service_date"])

    # Перенос дат из карточек. Следующий срок здесь не считаем: он зависит
    # от настроек и всегда вычисляется по карточке (модуль deadlines).
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        'SELECT id, last_recharge_date FROM "FireExtinguishers" '
        "WHERE last_recharge_date IS NOT NULL"
    )).fetchall()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
    for extinguisher_id, recharge_date in rows:
        conn.execute(
            sa.text(
                'INSERT INTO "ServiceRecords" (fire_extinguisher_id, service_date, recharged, '
                "tested, repaired, comments, created_at) "
                "VALUES (:fe, :day, 1, 0, 0, :comment, :now)"
            ),
            {"fe": extinguisher_id, "day": recharge_date,
             "comment": "Перенесено из карточки огнетушителя", "now": now},
        )


def downgrade() -> None:
    """Удаляет историю ТО и новые колонки."""
    op.drop_table("ServiceRecords")
    with op.batch_alter_table("Inspections") as batch:
        batch.drop_column("annul_reason")
        batch.drop_column("annulled_by")
        batch.drop_column("annulled_at")
    with op.batch_alter_table("FireExtinguishers") as batch:
        batch.drop_column("last_test_date")
        batch.drop_column("serial_number")
