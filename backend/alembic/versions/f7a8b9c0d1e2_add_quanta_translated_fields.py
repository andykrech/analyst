"""Add translated fields to theme_quanta

Revision ID: f7a8b9c0d1e2
Revises: 630ab6a11bd0
Create Date: 2026-02-21

Поля для отображения на основном языке темы (languages[0]): title_translated,
summary_text_translated, key_points_translated. Nullable — для квантов на том же языке,
что и основной, перевод не храним.

Запуск миграции изнутри контейнера (из хоста):
  docker compose -f infra/docker/docker-compose.yml exec backend alembic upgrade head
Внутри контейнера (если уже зашли в backend):
  alembic upgrade head
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "630ab6a11bd0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "theme_quanta",
        sa.Column(
            "title_translated",
            sa.Text(),
            nullable=True,
            comment="Заголовок на основном языке темы (languages[0]); NULL если язык кванта совпадает с основным",
        ),
    )
    op.add_column(
        "theme_quanta",
        sa.Column(
            "summary_text_translated",
            sa.Text(),
            nullable=True,
            comment="Описание на основном языке темы; NULL если язык кванта совпадает с основным",
        ),
    )
    op.add_column(
        "theme_quanta",
        sa.Column(
            "key_points_translated",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Ключевые пункты на основном языке темы (список строк); NULL если язык кванта совпадает с основным",
        ),
    )
    for col, comment in (
        ("title_translated", "Заголовок на основном языке темы (languages[0]); NULL если язык кванта совпадает с основным"),
        ("summary_text_translated", "Описание на основном языке темы; NULL если язык кванта совпадает с основным"),
        ("key_points_translated", "Ключевые пункты на основном языке темы (список строк); NULL если язык кванта совпадает с основным"),
    ):
        escaped = comment.replace("'", "''")
        op.execute(f"COMMENT ON COLUMN theme_quanta.{col} IS '{escaped}'")


def downgrade() -> None:
    op.drop_column("theme_quanta", "key_points_translated")
    op.drop_column("theme_quanta", "summary_text_translated")
    op.drop_column("theme_quanta", "title_translated")
