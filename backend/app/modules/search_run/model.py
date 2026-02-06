"""SQLAlchemy-модель для журнала запусков обработки темы."""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SearchRun(Base):
    """
    Журнал запусков обработки темы: backfill, update, rebuild_overview,
    fetch_content, rerank_sources и т.п. Нужен для прогресса, статусов,
    повторов и привязки артефактов к запуску.
    """

    __tablename__ = "search_runs"
    __table_args__ = (
        Index(
            "ix_search_runs_theme_id_active",
            "theme_id",
            "status",
            postgresql_where=text(
                "status IN ('queued', 'running') AND deleted_at IS NULL"
            ),
        ),
        Index(
            "uq_search_runs_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        {"comment": "Журнал запусков обработки темы (backfill, update, fetch_content и т.п.)"},
    )

    # --- Идентификация и связь ---
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Уникальный идентификатор запуска обработки темы.",
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Идентификатор темы (themes.id), для которой выполняется запуск.",
    )

    # --- Тип и статус ---
    run_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Тип запуска: backfill / update / rebuild_overview / fetch_content / rerank_sources / other.",
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="queued",
        comment="Статус запуска: queued / running / done / failed / canceled.",
    )

    # --- Время выполнения ---
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Когда запуск был поставлен в очередь.",
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда запуск фактически начался.",
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда запуск завершился (успех/ошибка/отмена).",
    )

    # --- Параметры и прогресс ---
    params: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Параметры запуска (языки, период, лимиты, настройки провайдера поиска и т.п.).",
    )
    progress: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Текущий прогресс выполнения (done_periods/total_periods, этап пайплайна).",
    )
    stats: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Итоговая статистика запуска (ссылок найдено, дайджестов создано и т.п.).",
    )

    # --- Ошибки и трассировка ---
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Краткое сообщение об ошибке (если запуск завершился с failed).",
    )
    error_details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Структурированные детали ошибки (stack trace, коды провайдера, контекст шагов).",
    )
    logs: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Опциональные структурированные логи по шагам (для отладки); в MVP может оставаться пустым.",
    )

    # --- Период обработки ---
    period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Начало периода, который покрывает запуск (например месяц при backfill или интервал обновления).",
    )
    period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Конец периода, который покрывает запуск.",
    )

    # --- Идемпотентность и управление повторными запусками ---
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        index=True,
        comment="Ключ идемпотентности для защиты от двойного запуска (например theme_id+run_type+period).",
    )
    triggered_by: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="system",
        comment="Кем запущено: system / user / admin.",
    )
    trigger_context: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Контекст запуска (user_action, причина планировщика, параметры UI).",
    )
    attempt: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
        comment="Номер попытки выполнения (1 — первый запуск, 2+ — ретраи).",
    )
    parent_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Ссылка на исходный запуск (если это повтор/ретрай).",
    )

    # --- Технические поля ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата/время создания записи запуска.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Дата/время последнего изменения записи запуска.",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Мягкое удаление записи запуска (обычно не нужно, но заложить).",
    )
