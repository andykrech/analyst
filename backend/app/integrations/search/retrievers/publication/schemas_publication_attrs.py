"""
Pydantic-схемы для attrs.publication (типоспецифичные поля кванта типа publication).
Не дублируют поля core-кванта: title, summary_text, date_at и т.д.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class PublicationAffiliation(BaseModel):
    """Аффилиация автора (институция)."""

    model_config = {"extra": "ignore"}

    id: str | None = None
    display_name: str | None = None
    ror: str | None = None
    country_code: str | None = None
    type: str | None = None


class PublicationAuthor(BaseModel):
    """Автор публикации (dehydrated или краткий)."""

    model_config = {"extra": "ignore"}

    id: str | None = None
    display_name: str | None = None
    orcid: str | None = None


class PublicationContributors(BaseModel):
    """Вклад авторов: автор + позиция + институции."""

    model_config = {"extra": "ignore"}

    author: PublicationAuthor | None = None
    author_position: str | None = None
    institutions: list[PublicationAffiliation] = Field(default_factory=list)


class PublicationVenue(BaseModel):
    """Площадка публикации (журнал, конференция)."""

    model_config = {"extra": "ignore"}

    id: str | None = None
    display_name: str | None = None
    issn_l: str | None = None
    issn: list[str] | None = None
    type: str | None = None
    url: HttpUrl | str | None = None


class PublicationBiblio(BaseModel):
    """Библиографические данные (том, выпуск, страницы)."""

    model_config = {"extra": "ignore"}

    volume: str | None = None
    issue: str | None = None
    first_page: str | None = None
    last_page: str | None = None


class PublicationAccess(BaseModel):
    """Доступность (OA статус)."""

    model_config = {"extra": "ignore"}

    is_oa: bool | None = None
    oa_status: str | None = None
    oa_url: str | HttpUrl | None = None
    any_repository_has_fulltext: bool | None = None


class PublicationMetrics(BaseModel):
    """Метрики (цитирования и т.п.)."""

    model_config = {"extra": "ignore"}

    cited_by_count: int | None = None
    fwci: float | None = None


class PublicationTopic(BaseModel):
    """Тема/концепт (display_name, id)."""

    model_config = {"extra": "ignore"}

    id: str | None = None
    display_name: str | None = None
    score: float | None = None
    level: int | None = None


class PublicationClassification(BaseModel):
    """Классификация (концепты/темы)."""

    model_config = {"extra": "ignore"}

    topics: list[PublicationTopic] = Field(default_factory=list)


class PublicationRelations(BaseModel):
    """Связи с другими работами (пока пустой)."""

    model_config = {"extra": "ignore"}


class PublicationSourceExtras(BaseModel):
    """Дополнительные данные от источника (extra='allow')."""

    model_config = {"extra": "allow"}

    openalex: dict[str, Any] | None = None


class PublicationAttrs(BaseModel):
    """Атрибуты кванта entity_kind=publication (attrs.publication)."""

    model_config = {"extra": "ignore"}

    work_type: str | None = None
    venue: PublicationVenue | None = None
    biblio: PublicationBiblio | None = None
    contributors: list[PublicationContributors] = Field(default_factory=list)
    access: PublicationAccess | None = None
    metrics: PublicationMetrics | None = None
    classification: PublicationClassification | None = None
    relations: PublicationRelations | None = None
    source_extras: PublicationSourceExtras | None = None
