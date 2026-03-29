"""Построение и сохранение ландшафта темы через LLM."""

from __future__ import annotations

import json
import logging
import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.llm import LLMService
from app.integrations.llm.types import GenerationParams
from app.integrations.prompts import PromptService
from app.modules.landscape.exceptions import LandscapePromptTooLargeError
from app.modules.landscape.model import Landscape
from app.modules.landscape.service import load_events_json_payload
from app.modules.theme.service import get_theme_with_queries


PROMPT_NAME = "landscape.build.v1"
_DEBUG_LOG_PATH = "logs/events_llm_debug.log"
logger = logging.getLogger(__name__)


def _get_debug_logger() -> logging.Logger:
    dbg = logging.getLogger("events_llm_debug")
    if not dbg.handlers:
        dbg.setLevel(logging.INFO)
        try:
            os.makedirs(os.path.dirname(_DEBUG_LOG_PATH) or ".", exist_ok=True)
            fh = logging.FileHandler(_DEBUG_LOG_PATH, encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
            dbg.addHandler(fh)
        except Exception as e:
            logger.warning("landscape_builder: failed to init debug logger: %s", e)
    return dbg


_debug_logger = _get_debug_logger()


class LandscapeBuilder:
    """Собирает промпт из описания темы и JSON событий, вызывает LLM, пишет версию в БД."""

    def __init__(
        self,
        *,
        llm_service: LLMService,
        prompt_service: PromptService,
        settings: Settings,
    ) -> None:
        self._llm = llm_service
        self._prompts = prompt_service
        self._settings = settings

    async def build(
        self,
        db: AsyncSession,
        *,
        theme_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Landscape:
        theme, _ = await get_theme_with_queries(db, theme_id, user_id)
        if not theme:
            raise ValueError("theme_not_found")

        description = (theme.description or "").strip()
        langs = theme.languages or []
        primary_language = str(langs[0]).strip() if isinstance(langs, list) and len(langs) > 0 else ""

        events_payload = await load_events_json_payload(db, theme_id=theme_id)
        events_json = json.dumps(
            events_payload,
            ensure_ascii=False,
            indent=2,
        )

        rendered = await self._prompts.render(
            PROMPT_NAME,
            {
                "theme_description": description,
                "primary_language": primary_language,
                "events_json": events_json,
            },
        )
        prompt_text = rendered.text
        limit = self._settings.LANDSCAPE_MAX_PROMPT_CHARS
        if len(prompt_text) > limit:
            raise LandscapePromptTooLargeError(
                f"Промпт слишком длинный: {len(prompt_text)} символов, лимит {limit}.",
                char_count=len(prompt_text),
                limit=limit,
            )
        try:
            _debug_logger.info(
                "theme_id=%s LANDSCAPE PROMPT (chars=%s):\n%s",
                theme_id,
                len(prompt_text),
                prompt_text,
            )
        except Exception:
            pass

        response = await self._llm.generate_text(
            [{"role": "system", "content": prompt_text}],
            task=PROMPT_NAME,
            generation=GenerationParams(
                temperature=0.3,
                max_tokens=self._settings.LANDSCAPE_MAX_OUTPUT_TOKENS,
                top_p=0.95,
            ),
            response_format="text",
            billing_session=db,
            billing_theme_id=theme_id,
        )
        body = (response.text or "").strip()
        try:
            _debug_logger.info(
                "theme_id=%s LANDSCAPE LLM RAW RESPONSE:\n%s",
                theme_id,
                body,
            )
        except Exception:
            pass
        if not body:
            raise ValueError("empty_llm_response")

        row = Landscape(theme_id=theme_id, text=body)
        db.add(row)
        await db.flush()
        return row
