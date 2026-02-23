"""
Роутер поиска: POST /api/v1/search/collect, POST /api/v1/search/collect-by-theme.
При collect-by-theme найденные кванты сохраняются в БД; перед записью поля переводятся на основной язык темы.
"""
import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.integrations.llm import LLMService, get_llm_service
from app.integrations.prompts import PromptService, get_prompt_service
from app.integrations.search.schemas import (
    QuantumCollectResult,
    SearchQuery,
    ThemeSearchCollectRequest,
    TimeSlice,
)
from app.integrations.search.service import SearchService
from app.integrations.translation import TranslationService
from app.modules.quanta.service import (
    get_translate_batch_count,
    save_quanta_from_search,
    translate_quanta_create_items,
)
from app.modules.theme.service import get_theme_by_id

router = APIRouter(prefix="/api/v1/search", tags=["search"])
logger = logging.getLogger(__name__)

# Секунд на один батч перевода; общий таймаут = число_батчей * SECONDS_PER_TRANSLATE_BATCH
SECONDS_PER_TRANSLATE_BATCH = 60


def get_search_service(request: Request) -> SearchService:
    """Возвращает SearchService из app.state (инициализируется при старте)."""
    return request.app.state.search_service


def get_translation_service(request: Request) -> TranslationService:
    """Возвращает TranslationService из app.state (при QUANTA_TRANSLATION_METHOD=translator)."""
    return request.app.state.translation_service


@router.post("/collect", response_model=QuantumCollectResult)
async def collect_links(
    body: SearchQuery,
    search_service: SearchService = Depends(get_search_service),
) -> QuantumCollectResult:
    """
    Legacy: собрать релевантные ссылки по поисковому запросу (SearchQuery).
    """
    return await search_service.collect_links(
        query=body,
        mode="discovery",
        request_id=None,
    )


@router.post("/collect-by-theme", response_model=QuantumCollectResult)
async def collect_links_by_theme(
    request: Request,
    body: ThemeSearchCollectRequest,
    db: AsyncSession = Depends(get_db),
    search_service: SearchService = Depends(get_search_service),
    llm_service: LLMService = Depends(get_llm_service),
    prompt_service: PromptService = Depends(get_prompt_service),
) -> QuantumCollectResult:
    """
    Собрать ссылки по теме из theme_search_queries.

    Если переданы published_from и published_to — создаётся TimeSlice,
    иначе time_slice = None (без фильтра по дате).
    Перед записью квантов поля title, summary_text, key_points переводятся на основной язык темы (theme.languages[0]).
    Метод перевода задаётся в конфиге: QUANTA_TRANSLATION_METHOD=translator (DeepL и др.) или llm (ИИ).
    """
    time_slice = None
    if body.published_from is not None and body.published_to is not None:
        time_slice = TimeSlice(
            published_from=body.published_from,
            published_to=body.published_to,
        )
    run_id_uuid: uuid.UUID | None = None
    if body.run_id and str(body.run_id).strip():
        try:
            run_id_uuid = uuid.UUID(str(body.run_id))
        except ValueError:
            pass
    result = await search_service.collect_links_for_theme(
        session=db,
        theme_id=body.theme_id,
        time_slice=time_slice,
        target_links=body.target_links,
        mode="default",
        request_id=None,
        run_id=body.run_id,
    )
    if result.items:
        theme_id_uuid: uuid.UUID | None = None
        try:
            theme_id_uuid = uuid.UUID(str(body.theme_id))
        except (ValueError, TypeError):
            pass
        primary_language = "en"
        if theme_id_uuid:
            theme = await get_theme_by_id(db, theme_id_uuid)
            if theme and theme.languages:
                primary_language = theme.languages[0] if theme.languages else "en"

        settings = get_settings()
        translations_by_index: dict[int, dict] = {}

        if settings.QUANTA_TRANSLATION_METHOD.strip().lower() == "translator":
            translation_service = get_translation_service(request)
            try:
                translations_by_index, cost = await translation_service.translate_quanta_create_items(
                    result.items,
                    target_lang=primary_language,
                )
                logger.info(
                    "collect-by-theme: перевод через %s, входящих символов=%s",
                    settings.TRANSLATOR,
                    cost.input_characters,
                )
            except Exception as e:
                logger.warning("collect-by-theme: ошибка перевода квантов (translator), сохраняем без переводов: %s", e)
        else:
            batch_count = get_translate_batch_count(
                result.items,
                primary_language,
                limit=settings.QUANTA_TRANSLATION_LIMIT,
            )
            translate_timeout_s = max(1, batch_count) * SECONDS_PER_TRANSLATE_BATCH
            try:
                translations_by_index = await asyncio.wait_for(
                    translate_quanta_create_items(
                        result.items,
                        primary_language,
                        llm_service,
                        prompt_service,
                        limit=settings.QUANTA_TRANSLATION_LIMIT,
                    ),
                    timeout=translate_timeout_s,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "collect-by-theme: перевод квантов (LLM) не уложился в %s с (батчей=%s), сохраняем без переводов",
                    translate_timeout_s,
                    batch_count,
                )
            except Exception as e:
                logger.warning("collect-by-theme: ошибка перевода квантов (LLM), сохраняем без переводов: %s", e)

        await save_quanta_from_search(
            db,
            result.items,
            run_id=run_id_uuid,
            translations_by_index=translations_by_index,
        )
    return result
