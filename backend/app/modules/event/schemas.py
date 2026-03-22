"""Pydantic-схемы для API событий (MVP)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EventExtractResponse(BaseModel):
    processed_quanta: int = Field(..., description="Сколько квантов обработано в рамках запроса")
    created_events: int = Field(..., description="Сколько событий создано в рамках запроса")


class EventOut(BaseModel):
    id: UUID
    theme_id: UUID
    plot_code: str | None = Field(None, description="Код сюжета события (EventPlot.code), если известен")
    plot_name: str | None = Field(None, description="Имя сюжета события (EventPlot.name), если известно")

    predicate_text: str
    predicate_normalized: str
    predicate_class: str | None = None

    display_text: str
    event_time: str | None = None

    created_at: datetime
    updated_at: datetime


class EventParticipantOut(BaseModel):
    role_code: str
    role_name: str | None = None
    entity_id: UUID
    entity_normalized_name: str
    entity_canonical_name: str | None = None


class EventAttributeOut(BaseModel):
    attribute_for: str
    entity_id: UUID | None = None
    entity_normalized_name: str | None = None
    attribute_text: str
    attribute_normalized: str | None = None


class EventDetailOut(BaseModel):
    event: EventOut
    participants: list[EventParticipantOut]
    attributes: list[EventAttributeOut]


