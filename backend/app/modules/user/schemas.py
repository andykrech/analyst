"""Схемы API для пользователя: ui_state."""

from typing import Any

from pydantic import BaseModel, Field


class UiStateGetResponse(BaseModel):
    """Ответ GET ui_state: состояние UI (active_theme_id, url и др.)."""

    state: dict[str, Any] = Field(
        default_factory=dict,
        description="Состояние UI: active_theme_id, url и др.",
    )


class UiStatePutRequest(BaseModel):
    """Тело PUT ui_state: частичное обновление состояния."""

    active_theme_id: str | None = Field(default=None, description="ID активной темы или null")
    url: str | None = Field(default=None, description="Текущий URL (вкладка)")
