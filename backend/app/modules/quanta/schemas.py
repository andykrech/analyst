"""Pydantic-схемы для квантов информации (theme_quanta)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class QuantumIdentifier(BaseModel):
    """Нормализованный идентификатор (doi, patent_number и т.п.)."""

    scheme: str = Field(..., min_length=1, max_length=64, description="Схема (doi, patent_number, ...)")
    value: str = Field(..., min_length=1, max_length=512, description="Значение идентификатора")
    is_primary: bool | None = Field(default=None, description="Признак основного идентификатора")

    @field_validator("scheme", "value", mode="before")
    @classmethod
    def strip_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v


class QuantumCreate(BaseModel):
    """Создание/сохранение кванта (для ретриверов и внутреннего API)."""

    theme_id: str = Field(..., description="UUID темы-владельца")
    run_id: Optional[str] = Field(None, description="UUID прогона поиска (опционально)")

    entity_kind: Literal["publication", "patent", "webpage"] = Field(
        ...,
        description="Класс кванта (тип сущности)",
    )

    title: str = Field(..., min_length=1, description="Заголовок/название объекта")
    summary_text: str = Field(..., min_length=1, description="Короткое описание/сниппет/аннотация")
    key_points: list[str] = Field(default_factory=list, description="Ключевые пункты (список строк)")

    language: Optional[str] = Field(None, description="Язык контента (ru/en/...)")
    date_at: Optional[datetime] = Field(None, description="Дата публикации/выхода объекта")

    verification_url: str = Field(..., min_length=1, description="Кликабельная ссылка для проверки")
    canonical_url: Optional[str] = Field(None, description="Канонический URL (нормализованный)")

    # Дедуп: ретривер может задать вручную; иначе будет вычислен.
    dedup_key: Optional[str] = Field(None, description="Ключ дедупликации внутри темы (опционально)")
    fingerprint: Optional[str] = Field(None, description="Fallback fingerprint (опционально)")

    identifiers: list[QuantumIdentifier] = Field(default_factory=list, description="Список идентификаторов")
    matched_terms: list[str] = Field(default_factory=list, description="Термы/слова, совпавшие при поиске")
    matched_term_ids: list[str] = Field(default_factory=list, description="ID термов темы (если есть справочник)")

    retriever_query: Optional[str] = Field(None, description="Реальная строка запроса в источник")
    rank_score: Optional[float] = Field(None, description="Оценка релевантности/ранга из источника")
    source_system: str = Field(..., min_length=1, description="Система-источник (OpenAlex, Lens, Web, ...)")
    site_id: Optional[str] = Field(None, description="UUID сайта (опционально)")
    retriever_name: str = Field(..., min_length=1, description="Имя ретривера/модуля")
    retriever_version: Optional[str] = Field(None, description="Версия ретривера (опционально)")

    attrs: dict[str, Any] = Field(default_factory=dict, description="Расширяемые поля без миграций")
    raw_payload_ref: Optional[str] = Field(None, description="Ссылка на сырой payload (UUID)")
    content_ref: Optional[str] = Field(None, description="Ссылка на извлеченный контент")

    @field_validator(
        "title",
        "summary_text",
        "verification_url",
        "canonical_url",
        "dedup_key",
        "fingerprint",
        "language",
        "retriever_query",
        "source_system",
        "retriever_name",
        "retriever_version",
        "site_id",
        "raw_payload_ref",
        "content_ref",
        mode="before",
    )
    @classmethod
    def strip_optional_strings(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return v


class QuantumOut(BaseModel):
    """Квант в ответах API."""

    id: str
    theme_id: str
    run_id: Optional[str] = None

    entity_kind: str
    title: str
    summary_text: str
    key_points: list[str]
    language: Optional[str] = None
    date_at: Optional[datetime] = None

    verification_url: str
    canonical_url: Optional[str] = None

    dedup_key: str
    fingerprint: str
    identifiers: list[dict]
    matched_terms: list
    matched_term_ids: list

    retriever_query: Optional[str] = None
    rank_score: Optional[float] = None
    source_system: str
    site_id: Optional[str] = None
    retriever_name: str
    retriever_version: Optional[str] = None
    retrieved_at: datetime

    attrs: dict[str, Any]
    raw_payload_ref: Optional[str] = None
    content_ref: Optional[str] = None

    status: str
    duplicate_of_id: Optional[str] = None

    created_at: datetime
    updated_at: datetime


class QuantumListOut(BaseModel):
    items: list[QuantumOut] = Field(default_factory=list)
    total: int = Field(..., ge=0)


class QuantumFilter(BaseModel):
    entity_kind: Optional[Literal["publication", "patent", "webpage"]] = None
    status: Optional[Literal["active", "duplicate", "rejected", "error"]] = None

