"""ORM: версии текстового ландшафта темы."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Landscape(Base):
    """Одна сохранённая версия ландшафта темы (история по theme_id)."""

    __tablename__ = "landscapes"
    __table_args__ = ({"comment": "Версии текстового ландшафта темы."},)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Идентификатор версии ландшафта.",
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        comment="Тема, к которой относится эта версия ландшафта.",
    )
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Сгенерированный текст ландшафта темы.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Время создания версии.",
    )
