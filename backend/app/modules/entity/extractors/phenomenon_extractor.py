"""Экстрактор сущностей типа phenomenon (явление) из текста кванта через LLM."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm import LLMService
from app.integrations.prompts import PromptService


logger = logging.getLogger(__name__)

PROMPT_NAME_PHENOMENON_EXTRACTOR = "entity.entities_extractor_phenomenon.v1"

VALID_MODIFIERS = frozenset({"up", "down", "stable", "unstable", "none"})


class PhenomenonCandidate(BaseModel):
    """Кандидат явления с модификатором и условием."""

    phenomenon: str
    modifier: str
    condition_text: str


class PhenomenonExtractorResult(BaseModel):
    """Результат извлечения явлений для одного текста."""

    phenomena: list[PhenomenonCandidate]


class PhenomenonEntitiesExtractor:
    """Экстрактор явлений (phenomenon) через LLM и промпт."""

    def __init__(self, llm_service: LLMService, prompt_service: PromptService) -> None:
        self._llm_service = llm_service
        self._prompt_service = prompt_service

    async def extract_for_text(
        self,
        text: str,
        *,
        billing_session: AsyncSession | None = None,
        billing_theme_id: uuid.UUID | None = None,
    ) -> PhenomenonExtractorResult:
        """
        Извлечь явления из текста одного кванта.
        Возвращает список кандидатов; для каждого modifier не из списка подставляется "none".
        """
        cleaned_text = (text or "").strip()
        if not cleaned_text:
            logger.debug("phenomenon_extractor: пустой текст, пропуск")
            return PhenomenonExtractorResult(phenomena=[])

        logger.info(
            "phenomenon_extractor: вызов LLM (длина текста=%s)",
            len(cleaned_text),
        )
        try:
            response = await self._llm_service.generate_from_prompt(
                PROMPT_NAME_PHENOMENON_EXTRACTOR,
                {"text": cleaned_text},
                self._prompt_service,
                billing_session=billing_session,
                billing_theme_id=billing_theme_id,
            )
        except Exception as e:
            logger.warning(
                "phenomenon_extractor: ошибка при вызове LLM: %s",
                e,
                exc_info=True,
            )
            raise

        raw_text = (response.text or "").strip()
        logger.info(
            "phenomenon_extractor: ответ LLM получен (длина raw=%s)",
            len(raw_text),
        )
        if not raw_text:
            logger.warning(
                "phenomenon_extractor: пустой ответ LLM для текста длиной %s символов",
                len(cleaned_text),
            )
            return PhenomenonExtractorResult(phenomena=[])

        text_for_json = raw_text
        if text_for_json.startswith("```"):
            lines = text_for_json.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text_for_json = "\n".join(lines).strip()
            logger.debug("phenomenon_extractor: снята обёртка markdown, длина=%s", len(text_for_json))

        try:
            data: Any = json.loads(text_for_json)
        except json.JSONDecodeError as e:
            preview = "\n".join(text_for_json.splitlines()[:20])
            logger.warning(
                "phenomenon_extractor: invalid JSON from LLM: %s; preview:\n%s",
                e,
                preview or "(пусто)",
            )
            raise

        logger.debug("phenomenon_extractor: JSON распарсен, ключи=%s", list(data.keys()) if isinstance(data, dict) else type(data))

        try:
            result = PhenomenonExtractorResult.model_validate(data)
        except ValidationError as e:
            preview = "\n".join(text_for_json.splitlines()[:20])
            logger.warning(
                "phenomenon_extractor: validation error for LLM JSON: %s; preview:\n%s",
                e,
                preview or "(пусто)",
            )
            raise

        corrected: list[PhenomenonCandidate] = []
        for cand in result.phenomena:
            mod = (cand.modifier or "").strip().lower()
            if mod not in VALID_MODIFIERS:
                corrected.append(
                    PhenomenonCandidate(
                        phenomenon=cand.phenomenon,
                        modifier="none",
                        condition_text=cand.condition_text or "",
                    )
                )
            else:
                corrected.append(cand)
        logger.info(
            "phenomenon_extractor: готово, явлений=%s",
            len(corrected),
        )
        return PhenomenonExtractorResult(phenomena=corrected)
