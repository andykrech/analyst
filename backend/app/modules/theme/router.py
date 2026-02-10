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
    TermTranslateIn,
    TermTranslationOut,
    TermsTranslateLLMMeta,
    TermsTranslateRequest,
    TermsTranslateResponse,
    ThemePrepareLLMMeta,
    ThemePrepareRequest,
    ThemePrepareResponse,
    ThemePrepareResult,
    TermDTO,
)

router = APIRouter(prefix="/api/v1/themes", tags=["themes"])
logger = logging.getLogger(__name__)

THEME_INIT_PROMPT = "theme.init"
DETAIL_TRUNCATE = 300
CONTEXT_MAX_LEN = 600

TERMS_TRANSLATE_PROMPT = "terms.translate"
TERMS_MAX = 50
TEXT_MAX_LEN = 120
TRANSLATION_DETAIL_TRUNCATE = 300


def _normalize_terms(value: Any) -> list[dict[str, str]]:
    """
    Привести к списку термов [{text, context}, ...].
    Поддерживает: None, list[str], str (через запятую), list[dict].
    """
    result: list[dict[str, str]] = []
    seen: set[str] = set()

    def add_item(text: str, context: str = "") -> None:
        t = text.strip()
        if not t:
            return
        lower = t.lower()
        if lower in seen:
            return
        seen.add(lower)
        ctx = (context or "").strip()
        if len(ctx) > CONTEXT_MAX_LEN:
            ctx = ctx[:CONTEXT_MAX_LEN]
        result.append({"text": t, "context": ctx})

    if value is None:
        return []

    if isinstance(value, str):
        for s in value.split(","):
            add_item(s, "")
        return result

    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                add_item(item, "")
            elif isinstance(item, dict):
                text = item.get("text")
                if text is not None:
                    add_item(str(text), str(item.get("context", "")))
        return result

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
            generation={"temperature": 0.2, "max_tokens": 2000},
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

    keywords = [TermDTO(**x) for x in _normalize_terms(data.get("keywords"))]
    must_have = [TermDTO(**x) for x in _normalize_terms(data.get("must_have"))]
    excludes = [TermDTO(**x) for x in _normalize_terms(data.get("excludes"))]

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


@router.post("/terms/translate", response_model=TermsTranslateResponse)
async def translate_terms(
    body: TermsTranslateRequest,
    llm_service: LLMService = Depends(get_llm_service),
    prompt_service: PromptService = Depends(get_prompt_service),
) -> TermsTranslateResponse:
    """
    Перевод терминов (ключевых слов) через LLM с поддержкой id, text, context.
    """
    terms = body.terms

    if not terms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Список terms не может быть пустым.",
        )
    if len(terms) > TERMS_MAX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Список terms не может содержать более {TERMS_MAX} элементов.",
        )

    ids_stripped = [t.id.strip() for t in terms]
    seen_ids: set[str] = set()
    for lid in ids_stripped:
        if lid in seen_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Дублирующиеся id в terms: {lid!r}",
            )
        seen_ids.add(lid)

    for t in terms:
        if not t.text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"text не может быть пустым после strip для id={t.id!r}",
            )

    normalized_terms: list[dict[str, str]] = []
    for t in terms:
        ctx = (t.context or "").strip()
        if len(ctx) > CONTEXT_MAX_LEN:
            ctx = ctx[:CONTEXT_MAX_LEN]
        normalized_terms.append({"id": t.id.strip(), "text": t.text.strip(), "context": ctx})

    try:
        response = await llm_service.generate_from_prompt(
            prompt_name=TERMS_TRANSLATE_PROMPT,
            vars={
                "source_language": body.source_language,
                "target_language": body.target_language,
                "terms": json.dumps(normalized_terms, ensure_ascii=False),
            },
            prompt_service=prompt_service,
            task="terms_translate",
            generation={"temperature": 0.1, "max_tokens": 1500},
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("terms_translate LLM call failed: %s", e)
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
            detail="LLM вернул пустой ответ для terms.translate",
        )

    try:
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            raw_text = "\n".join(
                line for line in lines if line.strip() and not line.strip().startswith("```")
            )
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        snippet = raw_text[:TRANSLATION_DETAIL_TRUNCATE] + (
            "..." if len(raw_text) > TRANSLATION_DETAIL_TRUNCATE else ""
        )
        logger.warning("terms_translate invalid JSON: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM вернул невалидный JSON для terms.translate. {e!s}. Ответ (начало): {snippet!r}",
        ) from e

    if not isinstance(data, dict) or "translations" not in data:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Ожидался JSON-объект с ключом translations.",
        )

    raw_translations = data.get("translations")
    if not isinstance(raw_translations, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="translations должен быть массивом объектов.",
        )

    input_ids = [t["id"] for t in normalized_terms]
    received_ids = set()
    translations_by_id: dict[str, TermTranslationOut] = {}

    for item in raw_translations:
        if not isinstance(item, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Каждый элемент translations должен быть объектом с id и translation.",
            )
        mid = (item.get("id") or "").strip()
        mtrans = (item.get("translation") or "").strip()
        if not mid:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="В ответе LLM присутствует элемент без id.",
            )
        if not mtrans:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LLM не вернул перевод (translation) для id={mid!r}.",
            )
        if mid in received_ids:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LLM вернул дублирующийся id: {mid!r}.",
            )
        received_ids.add(mid)
        translations_by_id[mid] = TermTranslationOut(id=mid, translation=mtrans)

    missing_ids = [iid for iid in input_ids if iid not in received_ids]
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM не вернул переводы для id: {missing_ids}",
        )

    extra_ids = [iid for iid in received_ids if iid not in set(input_ids)]
    if extra_ids:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM вернул лишние id: {extra_ids}",
        )

    ordered_translations = [translations_by_id[iid] for iid in input_ids]

    llm_meta = TermsTranslateLLMMeta(
        provider=response.provider,
        model=response.model,
        usage=response.usage.model_dump(mode="json"),
        cost=response.cost.model_dump(mode="json"),
        warnings=response.warnings or [],
    )

    logger.info(
        "terms_translate ok provider=%s usage_source=%s total_cost=%s",
        response.provider,
        response.usage.source,
        response.cost.total_cost,
    )

    return TermsTranslateResponse(translations=ordered_translations, llm=llm_meta)
