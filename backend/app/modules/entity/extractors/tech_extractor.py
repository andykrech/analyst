"""Экстрактор технологических сущностей (tech) из текста кванта через LLM."""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, ValidationError

from app.integrations.llm import LLMService
from app.integrations.prompts import PromptService


logger = logging.getLogger(__name__)

PROMPT_NAME_TECH_EXTRACTOR = "entity.entities_extractor_tech.v1"


class TechEntityCandidate(BaseModel):
    """Кандидат технологической сущности, извлечённый из текста."""

    canonical_name: str
    normalized_name: str


class TechExtractorResult(BaseModel):
    """Результат работы tech-экстрактора для одного текста."""

    entities: list[TechEntityCandidate]


class TechEntitiesExtractor:
    """Высокоуровневый экстрактор tech-сущностей через LLM и промпт."""

    def __init__(self, llm_service: LLMService, prompt_service: PromptService) -> None:
        self._llm_service = llm_service
        self._prompt_service = prompt_service

    async def extract_for_text(self, text: str) -> TechExtractorResult:
        """
        Извлечь tech-сущности из текста одного кванта.

        Возвращает TechExtractorResult, при ошибке парсинга/валидации бросает исключение.
        """
        cleaned_text = (text or "").strip()
        if not cleaned_text:
            return TechExtractorResult(entities=[])

        response = await self._llm_service.generate_from_prompt(
            PROMPT_NAME_TECH_EXTRACTOR,
            {"text": cleaned_text},
            self._prompt_service,
        )

        raw_text = (response.text or "").strip()
        if not raw_text:
            logger.warning("tech_extractor: пустой ответ LLM для текста длиной %s символов", len(cleaned_text))
            return TechExtractorResult(entities=[])

        # Убираем возможные markdown-обёртки ```json ... ```
        text_for_json = raw_text
        if text_for_json.startswith("```"):
            lines = text_for_json.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text_for_json = "\n".join(lines).strip()

        try:
            data: Any = json.loads(text_for_json)
        except json.JSONDecodeError as e:
            preview = "\n".join(text_for_json.splitlines()[:20])
            logger.warning(
                "tech_extractor: invalid JSON from LLM: %s; preview:\n%s",
                e,
                preview or "(пусто)",
            )
            raise

        try:
            result = TechExtractorResult.model_validate(data)
        except ValidationError as e:
            preview = "\n".join(text_for_json.splitlines()[:20])
            logger.warning(
                "tech_extractor: validation error for LLM JSON: %s; preview:\n%s",
                e,
                preview or "(пусто)",
            )
            raise

        return result

