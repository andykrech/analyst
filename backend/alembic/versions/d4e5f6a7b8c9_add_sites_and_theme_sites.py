"""Add sites and theme_sites tables, site_id to source_links

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4a5b6
Create Date: 2026-02-15

Таблицы sites (справочник доменов), theme_sites (связь тема-сайт),
колонка site_id в source_links.
БЕЗ backfill — в базе пока нет source_links или заполнение site_id не требуется.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sites",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Идентификатор сайта (домен как сущность).",
        ),
        sa.Column(
            "domain",
            sa.Text(),
            nullable=False,
            comment="Домен сайта в нижнем регистре, без схемы и пути (пример: example.com).",
        ),
        sa.Column(
            "display_name",
            sa.Text(),
            nullable=True,
            comment="Отображаемое имя сайта (опционально).",
        ),
        sa.Column(
            "homepage_url",
            sa.Text(),
            nullable=True,
            comment="Домашняя страница (опционально), полный URL.",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Описание тематики сайта для пользователя (что это за сайт, чем полезен).",
        ),
        sa.Column(
            "default_language",
            sa.Text(),
            nullable=True,
            comment="Основной язык сайта (например: ru, en).",
        ),
        sa.Column(
            "country",
            sa.Text(),
            nullable=True,
            comment="Страна/регион (например: RU, LV, US), если известно.",
        ),
        sa.Column(
            "trust_score",
            sa.Numeric(4, 3),
            nullable=True,
            comment="Оценка доверия/качества (0..1), если будет использоваться.",
        ),
        sa.Column(
            "quality_tier",
            sa.SmallInteger(),
            nullable=True,
            comment="Условная категория качества (например 1..5), опционально.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата создания записи.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата последнего обновления.",
        ),
        sa.CheckConstraint("domain = lower(domain)", name="ck_sites_domain_lower"),
        sa.PrimaryKeyConstraint("id"),
        comment="Глобальный справочник доменов (сайтов)",
    )
    op.create_unique_constraint("uq_sites_domain", "sites", ["domain"])

    op.create_table(
        "theme_sites",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Идентификатор связи 'тема-сайт'.",
        ),
        sa.Column(
            "theme_id",
            sa.UUID(),
            nullable=False,
            comment="Ссылка на тему.",
        ),
        sa.Column(
            "site_id",
            sa.UUID(),
            nullable=False,
            comment="Ссылка на сайт (домен).",
        ),
        sa.Column(
            "mode",
            sa.Text(),
            nullable=False,
            comment="Режим: include|exclude|prefer (включить, исключить, предпочесть).",
        ),
        sa.Column(
            "source",
            sa.Text(),
            nullable=False,
            comment="Источник добавления: ai_recommended|user_added|discovered|admin_seed.",
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            comment="Статус: active|muted|pending_review.",
        ),
        sa.Column(
            "confidence",
            sa.Numeric(4, 3),
            nullable=True,
            comment="Уверенность (0..1) для рекомендаций/автообнаружения.",
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=True,
            comment="Причина/пояснение (почему сайт добавлен, откуда взят).",
        ),
        sa.Column(
            "created_by_user_id",
            sa.UUID(),
            nullable=True,
            comment="Если добавил пользователь — кто именно.",
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
        sa.CheckConstraint(
            "mode IN ('include','exclude','prefer')",
            name="ck_theme_sites_mode",
        ),
        sa.CheckConstraint(
            "source IN ('ai_recommended','user_added','discovered','admin_seed')",
            name="ck_theme_sites_source",
        ),
        sa.CheckConstraint(
            "status IN ('active','muted','pending_review')",
            name="ck_theme_sites_status",
        ),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("theme_id", "site_id", name="uq_theme_sites_theme_id_site_id"),
        comment="Связь тема-сайт: режим, источник, статус",
    )
    op.create_index(
        op.f("ix_theme_sites_theme_id"),
        "theme_sites",
        ["theme_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_theme_sites_site_id"),
        "theme_sites",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_theme_sites_theme_id_mode",
        "theme_sites",
        ["theme_id", "mode"],
        unique=False,
    )
    op.create_index(
        "ix_theme_sites_theme_id_status",
        "theme_sites",
        ["theme_id", "status"],
        unique=False,
    )

    op.add_column(
        "source_links",
        sa.Column(
            "site_id",
            sa.UUID(),
            nullable=True,
            comment="Ссылка на справочник sites для домена источника.",
        ),
    )
    op.create_foreign_key(
        "fk_source_links_site_id_sites",
        "source_links",
        "sites",
        ["site_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_source_links_site_id"),
        "source_links",
        ["site_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_source_links_site_id"), table_name="source_links")
    op.drop_constraint(
        "fk_source_links_site_id_sites",
        "source_links",
        type_="foreignkey",
    )
    op.drop_column("source_links", "site_id")

    op.drop_index("ix_theme_sites_theme_id_status", table_name="theme_sites")
    op.drop_index("ix_theme_sites_theme_id_mode", table_name="theme_sites")
    op.drop_index(op.f("ix_theme_sites_site_id"), table_name="theme_sites")
    op.drop_index(op.f("ix_theme_sites_theme_id"), table_name="theme_sites")
    op.drop_table("theme_sites")

    op.drop_constraint("uq_sites_domain", "sites", type_="unique")
    op.drop_table("sites")
