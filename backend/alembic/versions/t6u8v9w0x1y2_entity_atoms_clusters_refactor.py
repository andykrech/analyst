"""Entity atoms/clusters architecture refactor

Revision ID: t6u8v9w0x1y2
Revises: s5t6u8v9w0x1
Create Date: 2026-03-14

Рефакторинг хранения сущностей: удаление entities/entity_aliases,
введение atoms, clusters, cluster_atoms. Связь event_participants.entity_id
переводится на clusters.id.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "t6u8v9w0x1y2"
down_revision: Union[str, Sequence[str], None] = "s5t6u8v9w0x1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Убрать зависимость event_participants от entities
    op.drop_constraint(
        "event_participants_entity_id_fkey",
        "event_participants",
        type_="foreignkey",
    )

    # 2) Удалить старые entity-таблицы (entity_aliases ссылается на entities)
    op.drop_table("entity_aliases")
    op.drop_table("entities")

    # 3) Таблица atoms
    op.create_table(
        "atoms",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор атома.",
        ),
        sa.Column(
            "theme_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор темы.",
        ),
        sa.Column(
            "lemma",
            sa.Text(),
            nullable=False,
            comment="Нормализованная лемма атома.",
        ),
        sa.Column(
            "global_cluster_df",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Глобальная документная частота атома по кластерам внутри темы.",
        ),
        sa.Column(
            "global_score",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Агрегированная глобальная оценка значимости атома внутри темы.",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        comment="Атомы сущностей по теме (минимальные смысловые единицы).",
    )
    op.create_index("ix_atoms_theme_id", "atoms", ["theme_id"], unique=False)
    op.create_unique_constraint(
        "uq_atoms_theme_id_lemma",
        "atoms",
        ["theme_id", "lemma"],
    )

    # 4) Таблица clusters
    op.create_table(
        "clusters",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор кластера.",
        ),
        sa.Column(
            "theme_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор темы.",
        ),
        sa.Column(
            "normalized_text",
            sa.Text(),
            nullable=False,
            comment="Нормализованный текст кластера (ключ уникальности в рамках темы).",
        ),
        sa.Column(
            "display_text",
            sa.Text(),
            nullable=False,
            comment="Отображаемый текст кластера.",
        ),
        sa.Column(
            "type",
            sa.Text(),
            nullable=False,
            server_default="other",
            comment="Тип кластера (например person/org/tech/phenomenon/other).",
        ),
        sa.Column(
            "global_df",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Глобальная документная частота кластера внутри темы.",
        ),
        sa.Column(
            "global_score",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Агрегированная глобальная оценка значимости кластера внутри темы.",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        comment="Кластеры сущностей по теме (составные сущности из атомов).",
    )
    op.create_index("ix_clusters_theme_id", "clusters", ["theme_id"], unique=False)
    op.create_unique_constraint(
        "uq_clusters_theme_id_normalized_text",
        "clusters",
        ["theme_id", "normalized_text"],
    )

    # 5) Таблица cluster_atoms
    op.create_table(
        "cluster_atoms",
        sa.Column(
            "cluster_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор кластера.",
        ),
        sa.Column(
            "atom_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор атома.",
        ),
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
            comment="Позиция атома в кластере.",
        ),
        sa.PrimaryKeyConstraint("cluster_id", "atom_id", "position"),
        sa.ForeignKeyConstraint(["cluster_id"], ["clusters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["atom_id"], ["atoms.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "cluster_id",
            "atom_id",
            "position",
            name="uq_cluster_atoms_cluster_atom_position",
        ),
        comment="Связь кластеров с атомами (состав и позиция).",
    )
    op.create_index("ix_cluster_atoms_cluster_id", "cluster_atoms", ["cluster_id"], unique=False)
    op.create_index("ix_cluster_atoms_atom_id", "cluster_atoms", ["atom_id"], unique=False)

    # 6) Связать event_participants.entity_id с clusters.id
    op.create_foreign_key(
        "event_participants_entity_id_fkey",
        "event_participants",
        "clusters",
        ["entity_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "event_participants_entity_id_fkey",
        "event_participants",
        type_="foreignkey",
    )
    op.drop_index("ix_cluster_atoms_atom_id", table_name="cluster_atoms")
    op.drop_index("ix_cluster_atoms_cluster_id", table_name="cluster_atoms")
    op.drop_table("cluster_atoms")
    op.drop_constraint("uq_clusters_theme_id_normalized_text", "clusters", type_="unique")
    op.drop_index("ix_clusters_theme_id", table_name="clusters")
    op.drop_table("clusters")
    op.drop_constraint("uq_atoms_theme_id_lemma", "atoms", type_="unique")
    op.drop_index("ix_atoms_theme_id", table_name="atoms")
    op.drop_table("atoms")
    # Старые таблицы entities/entity_aliases не восстанавливаем.
    # event_participants.entity_id остаётся без FK (данные не восстанавливаются).
