"""SQLAlchemy-модели для дайджестов и связи с источниками."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.modules.event.model import EventDigestLink
    from app.modules.source_link.model import SourceLink


class Digest(Base):
    """
    Периодические отчёты по теме (месячные/еженедельные/ежедневные).
    Строятся на наборе source_links. Поддерживают compaction/retention:
    hot/warm/cold, удаление тяжёлых полей, архивные краткие версии.
    """

    __tablename__ = "digests"
    __table_args__ = (
        Index(
            "uq_digests_theme_type_period",
            "theme_id",
            "digest_type",
            "period_start",
            "period_end",
            unique=True,
            postgresql_where=text(
                "deleted_at IS NULL AND previous_digest_id IS NULL"
            ),
        ),
        {"comment": "Периодические дайджесты по теме с поддержкой compaction/retention"},
    )

    # --- Идентификация и связи ---
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор дайджеста.",
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Идентификатор темы, к которой относится дайджест.",
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Идентификатор запуска (search_runs), в рамках которого был создан/пересобран дайджест.",
    )

    # --- Тип и период ---
    digest_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="period",
        comment="Тип дайджеста: monthly / weekly / daily / period / other (строкой, без enum).",
    )
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Начало периода, который покрывает дайджест.",
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Конец периода, который покрывает дайджест.",
    )
    period_label: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Человекочитаемая метка периода для UI (например '2025-01' для месяца).",
    )

    # --- Статус генерации ---
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="queued",
        comment="Статус генерации: queued / running / done / failed.",
    )
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Когда дайджест был поставлен в очередь на генерацию.",
    )
    generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда дайджест был успешно сгенерирован (status=done).",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Краткое сообщение об ошибке генерации (status=failed).",
    )
    error_details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Структурированные детали ошибки/контекста генерации.",
    )

    # --- Содержимое (полная версия, hot) ---
    content_md: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Полный текст дайджеста в Markdown (может быть очищен при compaction).",
    )
    bullets: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Ключевые пункты дайджеста (список строк/объектов), может быть оставлен даже при compaction.",
    )
    highlights: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Выделенные важные моменты/инсайты (структурировано), может быть очищено при compaction.",
    )

    # --- Структуры смысла (JSON) ---
    entities: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Сущности, извлечённые из дайджеста (канонические имена/алиасы/веса).",
    )
    events: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="События, извлечённые из дайджеста (структурированные факты, участники, время, источники).",
    )
    subtopics: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Подтемы, обнаруженные в рамках периода.",
    )
    signals: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Сигналы (слабые признаки изменений) в периоде.",
    )
    trends: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Тренды, наблюдаемые в периоде (локальные/срез периода).",
    )
    drivers: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Внешние драйверы, замеченные в периоде.",
    )
    scenarios: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Сценарии/гипотезы, сформулированные на основе периода (обычно кратко).",
    )

    # --- Метрики периода ---
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Метрики периода (attention index, novelty, частоты сущностей и др.).",
    )

    # --- Compaction/Retention ---
    storage_tier: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="hot",
        comment="Слой хранения: hot / warm / cold. Hot = полный контент, Warm = укороченный/сжатый, Cold = только минимальные поля.",
    )
    is_compacted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Признак, что дайджест был уплотнён (тяжёлые поля очищены/сжаты).",
    )
    compacted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда выполнена компактация (retention).",
    )
    content_deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда был очищен полный текст content_md (если удалён).",
    )
    compact_summary_md: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Архивная краткая версия дайджеста (Markdown), сохраняется после компактации.",
    )
    compact_bullets: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Архивные ключевые пункты (коротко) для warm/cold.",
    )
    compact_meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Метаданные компактации (что очищено, какие правила применены, размеры до/после).",
    )

    # --- Управление прочитанностью/видимостью ---
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда пользователь открыл/прочитал дайджест (для подсветки непрочитанного).",
    )
    pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Закреплён ли дайджест пользователем (исключение из агрессивной компактации).",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Заметки пользователя по дайджесту (на будущее).",
    )

    # --- Версионирование/пересборки ---
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
        comment="Версия дайджеста для данного периода (1 — первая генерация, 2+ — пересборки).",
    )
    previous_digest_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Ссылка на предыдущую версию дайджеста (если пересобран).",
    )

    # --- Технические поля ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата/время создания записи дайджеста.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Дата/время последнего изменения записи дайджеста.",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Мягкое удаление дайджеста (soft delete).",
    )

    # --- Связь с источниками (many-to-many через ассоциацию) ---
    digest_source_links: Mapped[list["DigestSourceLink"]] = relationship(
        "DigestSourceLink",
        back_populates="digest",
        cascade="all, delete-orphan",
    )
    # --- Связь с событиями (через event_digests) ---
    event_digest_links: Mapped[list["EventDigestLink"]] = relationship(
        "EventDigestLink",
        back_populates="digest",
    )


class DigestSourceLink(Base):
    """
    Связь дайджеста с источниками: какие source_links использовались
    для генерации дайджеста (many-to-many с доп. полями).
    """

    __tablename__ = "digest_source_links"
    __table_args__ = (
        {"comment": "Связь дайджестов с источниками (какие источники вошли в дайджест)"},
    )

    digest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("digests.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Идентификатор дайджеста.",
    )
    source_link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_links.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Идентификатор источника, использованного в дайджесте.",
    )
    role: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="input",
        comment="Роль источника: input / evidence / excluded / other.",
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Когда источник был добавлен в состав дайджеста.",
    )
    rank: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Позиция/ранг источника в отборе для дайджеста (если используется).",
    )

    digest: Mapped["Digest"] = relationship("Digest", back_populates="digest_source_links")
    source_link: Mapped["SourceLink"] = relationship(
        "SourceLink",
        back_populates="digest_source_links",
    )
