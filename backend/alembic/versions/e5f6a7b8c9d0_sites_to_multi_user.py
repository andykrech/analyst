"""Refactor sites to multi-user: add user_sites, remove user fields from sites

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-15

- sites: только глобальные поля (domain, default_language, country, timestamps)
- user_sites: пользовательские атрибуты (display_name, description и т.д.)
- БЕЗ backfill, таблицы пустые.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Удалить пользовательские поля из sites
    op.drop_column("sites", "display_name")
    op.drop_column("sites", "homepage_url")
    op.drop_column("sites", "description")
    op.drop_column("sites", "trust_score")
    op.drop_column("sites", "quality_tier")

    # 2. Создать таблицу user_sites
    op.create_table(
        "user_sites",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Идентификатор записи.",
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            nullable=False,
            comment="Пользователь.",
        ),
        sa.Column(
            "site_id",
            sa.UUID(),
            nullable=False,
            comment="Сайт (домен).",
        ),
        sa.Column(
            "display_name",
            sa.Text(),
            nullable=True,
            comment="Пользовательское отображаемое имя сайта.",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Пользовательское описание тематики сайта.",
        ),
        sa.Column(
            "homepage_url",
            sa.Text(),
            nullable=True,
            comment="Пользовательский URL.",
        ),
        sa.Column(
            "trust_score",
            sa.Numeric(4, 3),
            nullable=True,
            comment="Пользовательская оценка доверия (0..1).",
        ),
        sa.Column(
            "quality_tier",
            sa.SmallInteger(),
            nullable=True,
            comment="Пользовательская категория качества.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата создания.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата изменения.",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "site_id", name="uq_user_sites_user_id_site_id"),
        comment="Пользовательские атрибуты сайтов",
    )
    op.create_index(
        op.f("ix_user_sites_user_id"),
        "user_sites",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_sites_site_id"),
        "user_sites",
        ["site_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_sites_site_id"), table_name="user_sites")
    op.drop_index(op.f("ix_user_sites_user_id"), table_name="user_sites")
    op.drop_table("user_sites")

    op.add_column(
        "sites",
        sa.Column(
            "display_name",
            sa.Text(),
            nullable=True,
            comment="Отображаемое имя сайта (опционально).",
        ),
    )
    op.add_column(
        "sites",
        sa.Column(
            "homepage_url",
            sa.Text(),
            nullable=True,
            comment="Домашняя страница (опционально), полный URL.",
        ),
    )
    op.add_column(
        "sites",
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Описание тематики сайта для пользователя.",
        ),
    )
    op.add_column(
        "sites",
        sa.Column(
            "trust_score",
            sa.Numeric(4, 3),
            nullable=True,
            comment="Оценка доверия/качества (0..1).",
        ),
    )
    op.add_column(
        "sites",
        sa.Column(
            "quality_tier",
            sa.SmallInteger(),
            nullable=True,
            comment="Условная категория качества (1..5).",
        ),
    )
