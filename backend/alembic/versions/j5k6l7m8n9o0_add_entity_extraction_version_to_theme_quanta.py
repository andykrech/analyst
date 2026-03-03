"""Add entity_extraction_version column to theme_quanta.

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m9n0
Create Date: 2026-03-03

Добавляет поле entity_extraction_version в таблицу квантов для отслеживания версии экстрактора сущностей.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j5k6l7m8n9o0"
down_revision: Union[str, Sequence[str], None] = "i4j5k6l7m9n0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем nullable-колонку без server_default: для всех существующих строк значение будет NULL
    op.add_column(
        "theme_quanta",
        sa.Column(
            "entity_extraction_version",
            sa.Text(),
            nullable=True,
            comment=(
                "Версия экстрактора сущностей, которая использовалась для извлечения "
                "сущностей из этого кванта, если null - значит извлечение еще не "
                "производилось"
            ),
        ),
    )


def downgrade() -> None:
    # Откат: просто удаляем колонку, данные по версиям экстрактора теряются
    op.drop_column("theme_quanta", "entity_extraction_version")

