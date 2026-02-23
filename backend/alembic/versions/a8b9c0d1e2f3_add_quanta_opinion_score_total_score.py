"""Add opinion_score and total_score to theme_quanta

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-02-23

Поля для мнений ИИ о релевантности (opinion_score) и итоговой оценки (total_score).

Запуск миграции из контейнера (с хоста):
  docker compose -f infra/docker/docker-compose.yml exec backend alembic upgrade head
Внутри контейнера (если уже зашли в backend):
  alembic upgrade head
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "theme_quanta",
        sa.Column(
            "opinion_score",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Список мнений о релевантности кванта различных моделей ИИ",
        ),
    )
    op.add_column(
        "theme_quanta",
        sa.Column(
            "total_score",
            sa.Float(),
            nullable=True,
            comment="Итоговая оценка релевантности",
        ),
    )
    op.execute("COMMENT ON COLUMN theme_quanta.opinion_score IS 'Список мнений о релевантности кванта различных моделей ИИ'")
    op.execute("COMMENT ON COLUMN theme_quanta.total_score IS 'Итоговая оценка релевантности'")


def downgrade() -> None:
    op.drop_column("theme_quanta", "total_score")
    op.drop_column("theme_quanta", "opinion_score")
