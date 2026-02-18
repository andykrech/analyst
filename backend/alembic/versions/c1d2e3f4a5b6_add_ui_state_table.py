"""Add ui_state table

Revision ID: c1d2e3f4a5b6
Revises: fa1b2c3d4e5
Create Date: 2026-02-13

Таблица состояния UI пользователя (активная тема, вкладка и др.) для синхронизации между устройствами.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "fa1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ui_state",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            comment="Уникальный идентификатор записи",
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            nullable=False,
            comment="Пользователь (одна запись на пользователя)",
        ),
        sa.Column(
            "state_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Состояние UI в виде JSON (active_theme_id, active_tab и др.)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время последнего обновления",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        comment="Состояние UI пользователя (тема, вкладка и др.)",
    )
    op.create_index(
        op.f("ix_ui_state_user_id"),
        "ui_state",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_ui_state_user_id"), table_name="ui_state")
    op.drop_table("ui_state")
