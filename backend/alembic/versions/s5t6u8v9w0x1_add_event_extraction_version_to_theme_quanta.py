"""Add event_extraction_version to theme_quanta

Revision ID: s5t6u8v9w0x1
Revises: r4s5t6u8v9w0
Create Date: 2026-03-06

Добавляет поле event_extraction_version в таблицу theme_quanta для отметки версии
извлечения событий по каждому кванту.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "s5t6u8v9w0x1"
down_revision: Union[str, Sequence[str], None] = "r4s5t6u8v9w0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "theme_quanta",
        sa.Column(
            "event_extraction_version",
            sa.Text(),
            nullable=True,
            comment=(
                "Версия экстрактора событий, которая использовалась для извлечения "
                "событий из этого кванта; если null — извлечение ещё не выполнялось"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("theme_quanta", "event_extraction_version")

