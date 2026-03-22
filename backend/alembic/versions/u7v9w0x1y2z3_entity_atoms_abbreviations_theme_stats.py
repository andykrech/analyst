"""Entity: specificity_score, abbreviations, theme_stats

Revision ID: u7v9w0x1y2z3
Revises: t6u8v9w0x1y2
Create Date: 2026-03-14

Добавляет поле specificity_score в atoms; таблицы abbreviations,
abbreviation_atoms, abbreviation_clusters, theme_stats.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "u7v9w0x1y2z3"
down_revision: Union[str, Sequence[str], None] = "t6u8v9w0x1y2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "atoms",
        sa.Column(
            "specificity_score",
            sa.Float(),
            nullable=True,
            comment="Оценка специфичности атома от 0 до 1 (1 — узкий термин, 0 — общий).",
        ),
    )

    op.create_table(
        "abbreviations",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор записи аббревиатуры.",
        ),
        sa.Column(
            "theme_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор темы.",
        ),
        sa.Column(
            "abbreviation",
            sa.Text(),
            nullable=False,
            comment="Текст аббревиатуры.",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        comment="Аббревиатуры по теме для резолва при извлечении сущностей.",
    )
    op.create_index("ix_abbreviations_theme_id", "abbreviations", ["theme_id"], unique=False)

    op.create_table(
        "abbreviation_atoms",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор связи аббревиатура–атом.",
        ),
        sa.Column(
            "abbreviation_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор аббревиатуры.",
        ),
        sa.Column(
            "atom_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор атома.",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["abbreviation_id"], ["abbreviations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["atom_id"], ["atoms.id"], ondelete="CASCADE"),
        comment="Связь аббревиатур с атомами.",
    )
    op.create_index(
        "ix_abbreviation_atoms_abbreviation_id",
        "abbreviation_atoms",
        ["abbreviation_id"],
        unique=False,
    )
    op.create_index(
        "ix_abbreviation_atoms_atom_id",
        "abbreviation_atoms",
        ["atom_id"],
        unique=False,
    )

    op.create_table(
        "abbreviation_clusters",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор связи аббревиатура–кластер.",
        ),
        sa.Column(
            "abbreviation_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор аббревиатуры.",
        ),
        sa.Column(
            "cluster_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор кластера.",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["abbreviation_id"], ["abbreviations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cluster_id"], ["clusters.id"], ondelete="CASCADE"),
        comment="Связь аббревиатур с кластерами.",
    )
    op.create_index(
        "ix_abbreviation_clusters_abbreviation_id",
        "abbreviation_clusters",
        ["abbreviation_id"],
        unique=False,
    )
    op.create_index(
        "ix_abbreviation_clusters_cluster_id",
        "abbreviation_clusters",
        ["cluster_id"],
        unique=False,
    )

    op.create_table(
        "theme_stats",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Уникальный идентификатор записи статистики темы.",
        ),
        sa.Column(
            "theme_id",
            sa.UUID(),
            nullable=False,
            comment="Идентификатор темы.",
        ),
        sa.Column(
            "max_cluster_df",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Максимальная документная частота кластера в теме (для расчёта global_score кластеров).",
        ),
        sa.Column(
            "max_atom_cluster_df",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Максимальная частота атома по кластерам в теме (для расчёта global_score атомов).",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        comment="Статистика по теме (максимальные частоты для расчёта global_score).",
    )
    op.create_index("ix_theme_stats_theme_id", "theme_stats", ["theme_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_theme_stats_theme_id", table_name="theme_stats")
    op.drop_table("theme_stats")
    op.drop_index("ix_abbreviation_clusters_cluster_id", table_name="abbreviation_clusters")
    op.drop_index("ix_abbreviation_clusters_abbreviation_id", table_name="abbreviation_clusters")
    op.drop_table("abbreviation_clusters")
    op.drop_index("ix_abbreviation_atoms_atom_id", table_name="abbreviation_atoms")
    op.drop_index("ix_abbreviation_atoms_abbreviation_id", table_name="abbreviation_atoms")
    op.drop_table("abbreviation_atoms")
    op.drop_index("ix_abbreviations_theme_id", table_name="abbreviations")
    op.drop_table("abbreviations")
    op.drop_column("atoms", "specificity_score")
