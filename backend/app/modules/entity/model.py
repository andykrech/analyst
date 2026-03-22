"""SQLAlchemy-модели атомов и кластеров сущностей по теме."""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import Float, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Atom(Base):
    """Минимальная смысловая единица: нормализованный атом в рамках темы."""

    __tablename__ = "atoms"
    __table_args__ = (
        UniqueConstraint("theme_id", "lemma", name="uq_atoms_theme_id_lemma"),
        Index("ix_atoms_theme_id", "theme_id"),
        {"comment": "Атомы сущностей по теме (минимальные смысловые единицы)."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор атома.",
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Идентификатор темы.",
    )
    lemma: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Нормализованная лемма атома.",
    )
    global_cluster_df: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Глобальная документная частота атома по кластерам внутри темы.",
    )
    global_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default=text("0"),
        comment="Агрегированная глобальная оценка значимости атома внутри темы.",
    )
    specificity_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Оценка специфичности атома от 0 до 1 (1 — узкий термин, 0 — общий).",
    )

    cluster_atoms: Mapped[List["ClusterAtom"]] = relationship(
        "ClusterAtom",
        back_populates="atom",
        cascade="all, delete-orphan",
    )
    abbreviation_atoms: Mapped[List["AbbreviationAtom"]] = relationship(
        "AbbreviationAtom",
        back_populates="atom",
        cascade="all, delete-orphan",
    )


class Cluster(Base):
    """Составная сущность/кластер по теме, состоящий из атомов."""

    __tablename__ = "clusters"
    __table_args__ = (
        UniqueConstraint("theme_id", "normalized_text", name="uq_clusters_theme_id_normalized_text"),
        Index("ix_clusters_theme_id", "theme_id"),
        {"comment": "Кластеры сущностей по теме (составные сущности из атомов)."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор кластера.",
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Идентификатор темы.",
    )
    normalized_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Нормализованный текст кластера (ключ уникальности в рамках темы).",
    )
    display_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Отображаемый текст кластера.",
    )
    type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="other",
        comment="Тип кластера (например person/org/tech/phenomenon/other).",
    )
    global_df: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Глобальная документная частота кластера внутри темы.",
    )
    global_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default=text("0"),
        comment="Агрегированная глобальная оценка значимости кластера внутри темы.",
    )

    cluster_atoms: Mapped[List["ClusterAtom"]] = relationship(
        "ClusterAtom",
        back_populates="cluster",
        cascade="all, delete-orphan",
        order_by="ClusterAtom.position",
    )
    abbreviation_clusters: Mapped[List["AbbreviationCluster"]] = relationship(
        "AbbreviationCluster",
        back_populates="cluster",
        cascade="all, delete-orphan",
    )


class ClusterAtom(Base):
    """Связь кластера с атомами (состав кластера и порядок)."""

    __tablename__ = "cluster_atoms"
    __table_args__ = (
        UniqueConstraint(
            "cluster_id",
            "atom_id",
            "position",
            name="uq_cluster_atoms_cluster_atom_position",
        ),
        Index("ix_cluster_atoms_cluster_id", "cluster_id"),
        Index("ix_cluster_atoms_atom_id", "atom_id"),
        {"comment": "Связь кластеров с атомами (состав и позиция)."},
    )

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clusters.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        comment="Идентификатор кластера.",
    )
    atom_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("atoms.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        comment="Идентификатор атома.",
    )
    position: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        nullable=False,
        comment="Позиция атома в кластере.",
    )

    cluster: Mapped["Cluster"] = relationship(
        "Cluster",
        back_populates="cluster_atoms",
    )
    atom: Mapped["Atom"] = relationship(
        "Atom",
        back_populates="cluster_atoms",
    )


class Abbreviation(Base):
    """Аббревиатура в рамках темы с привязкой к атомам и кластерам."""

    __tablename__ = "abbreviations"
    __table_args__ = (
        Index("ix_abbreviations_theme_id", "theme_id"),
        {"comment": "Аббревиатуры по теме для резолва при извлечении сущностей."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор записи аббревиатуры.",
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Идентификатор темы.",
    )
    abbreviation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Текст аббревиатуры.",
    )

    abbreviation_atoms: Mapped[List["AbbreviationAtom"]] = relationship(
        "AbbreviationAtom",
        back_populates="abbreviation",
        cascade="all, delete-orphan",
    )
    abbreviation_clusters: Mapped[List["AbbreviationCluster"]] = relationship(
        "AbbreviationCluster",
        back_populates="abbreviation",
        cascade="all, delete-orphan",
    )


class AbbreviationAtom(Base):
    """Связь аббревиатуры с атомом."""

    __tablename__ = "abbreviation_atoms"
    __table_args__ = (
        Index("ix_abbreviation_atoms_abbreviation_id", "abbreviation_id"),
        Index("ix_abbreviation_atoms_atom_id", "atom_id"),
        {"comment": "Связь аббревиатур с атомами."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор связи аббревиатура–атом.",
    )
    abbreviation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("abbreviations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Идентификатор аббревиатуры.",
    )
    atom_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("atoms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Идентификатор атома.",
    )

    abbreviation: Mapped["Abbreviation"] = relationship(
        "Abbreviation",
        back_populates="abbreviation_atoms",
    )
    atom: Mapped["Atom"] = relationship("Atom", back_populates="abbreviation_atoms")


class AbbreviationCluster(Base):
    """Связь аббревиатуры с кластером."""

    __tablename__ = "abbreviation_clusters"
    __table_args__ = (
        Index("ix_abbreviation_clusters_abbreviation_id", "abbreviation_id"),
        Index("ix_abbreviation_clusters_cluster_id", "cluster_id"),
        {"comment": "Связь аббревиатур с кластерами."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор связи аббревиатура–кластер.",
    )
    abbreviation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("abbreviations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Идентификатор аббревиатуры.",
    )
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clusters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Идентификатор кластера.",
    )

    abbreviation: Mapped["Abbreviation"] = relationship(
        "Abbreviation",
        back_populates="abbreviation_clusters",
    )
    cluster: Mapped["Cluster"] = relationship(
        "Cluster",
        back_populates="abbreviation_clusters",
    )


class ThemeStats(Base):
    """Статистика по теме для нормализации оценок (max_cluster_df, max_atom_cluster_df)."""

    __tablename__ = "theme_stats"
    __table_args__ = (
        Index("ix_theme_stats_theme_id", "theme_id"),
        {"comment": "Статистика по теме (максимальные частоты для расчёта global_score)."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор записи статистики темы.",
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Идентификатор темы.",
    )
    max_cluster_df: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Максимальная документная частота кластера в теме (для расчёта global_score кластеров).",
    )
    max_atom_cluster_df: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Максимальная частота атома по кластерам в теме (для расчёта global_score атомов).",
    )
