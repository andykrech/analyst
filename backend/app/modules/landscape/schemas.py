"""Схемы API ландшафта темы."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LandscapeOut(BaseModel):
    id: UUID
    theme_id: UUID
    text: str = Field(..., description="Текст ландшафта")
    created_at: datetime = Field(..., description="Время создания версии")
