"""
Роутер тем: подготовка по сырому вводу (theme.init), CRUD (позже).
"""
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.integrations.llm import LLMService, get_llm_service
from app.integrations.prompts import PromptService, get_prompt_service
from app.modules.theme.schemas import (
    ThemePrepareLLMMeta,
    ThemePrepareRequest,
    ThemePrepareResponse,
    ThemePrepareResult,
)

router = APIRouter(prefix="/api/v1/themes", tags=["themes"])
logger = logging.getLogger(__name__)

THEME_INIT_PROMPT = "theme.init"
DETAIL_TRUNCATE = 300


def _normalize_string_list(value: Any) -> list[str]:
    """Привести к списку строк: список — как есть (элементы str); строка — split по запятой."""
    if isinstance(value, list):
        return [str(x).strip() for x in value if x is not None and str(x).strip()]
    if isinstance(value, str):
        return [s.strip() for s in value.split(",") if s.strip()]
    return []


@router.post("/prepare", response_model=ThemePrepareResponse)
async def prepare_theme(
    request: Request,
    body: ThemePrepareRequest,
    llm_service: LLMService = Depends(get_llm_service),
    prompt_service: PromptService = Depends(get_prompt_service),
) -> ThemePrepareResponse:
    """
    Подготовка темы по сырому вводу: вызов промпта theme.init, парсинг JSON.
    Не сохраняет тему в БД — только тест обработки.
    """
    try:
        response = await llm_service.generate_from_prompt(
            prompt_name=THEME_INIT_PROMPT,
            vars={"user_input": body.user_input},
            prompt_service=prompt_service,
            task="theme_init",
            generation={"temperature": 0.2, "max_tokens": 500},
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("theme_init LLM call failed: %s", e)
        msg = str(e)
        if "timeout" in msg.lower() or "timed out" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Таймаут при обращении к LLM. Попробуйте позже.",
            ) from e
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Ошибка при обращении к LLM. Проверьте настройки провайдера.",
        ) from e

    raw_text = (response.text or "").strip()
    if not raw_text:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM вернул пустой ответ для theme.init",
        )

    try:
        # Убрать возможную обёртку в ```json ... ```
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            raw_text = "\n".join(
                line for line in lines if line.strip() and not line.strip().startswith("```")
            )
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        snippet = raw_text[:DETAIL_TRUNCATE] + ("..." if len(raw_text) > DETAIL_TRUNCATE else "")
        logger.warning("theme_init invalid JSON: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM вернул невалидный JSON для theme.init. {e!s}. Ответ (начало): {snippet!r}",
        ) from e

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Ожидался JSON-объект с полями title, keywords, must_have, excludes.",
        )

    title = data.get("title")
    if not title or not str(title).strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="В ответе LLM отсутствует непустое поле title.",
        )
    title = str(title).strip()

    keywords = _normalize_string_list(data.get("keywords"))
    must_have = _normalize_string_list(data.get("must_have"))
    excludes = _normalize_string_list(data.get("excludes"))

    result = ThemePrepareResult(title=title, keywords=keywords, must_have=must_have, excludes=excludes)

    llm_meta = ThemePrepareLLMMeta(
        provider=response.provider,
        model=response.model,
        usage=response.usage.model_dump(mode="json"),
        cost=response.cost.model_dump(mode="json"),
        warnings=response.warnings or [],
    )

    logger.info(
        "theme_init ok task=theme_init provider=%s usage_source=%s total_cost=%s",
        response.provider,
        response.usage.source,
        response.cost.total_cost,
    )

    return ThemePrepareResponse(result=result, llm=llm_meta)
