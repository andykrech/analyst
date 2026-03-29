"""
Роутер поиска: POST /api/v1/search/collect, POST /api/v1/search/collect-by-theme.
При collect-by-theme найденные кванты сохраняются в БД; перед записью поля переводятся на основной язык темы.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import literal

from app.core.config import get_settings
from app.db.session import get_db
from app.integrations.embedding.model import Embedding
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
from app.modules.quanta.crud import record_rejected_quanta_candidates
from app.modules.quanta.service import (
    get_translate_batch_count,
    save_quanta_from_search,
    score_quanta_relevance,
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
        relevance_by_index: dict[int, dict] = {}
        items_to_save = result.items

        # Сначала оценка релевантности ИИ и фильтр по total_score — потом переводим только то, что сохраняем
        if result.items and theme_id_uuid and theme:
            theme_description = (theme.description or theme.title or "").strip()
            try:
                relevance_list = await score_quanta_relevance(
                    theme_description,
                    result.items,
                    model_names=["deepseek"],
                    llm_service=llm_service,
                    prompt_service=prompt_service,
                    billing_session=db,
                    billing_theme_id=theme_id_uuid,
                )
                total_threshold = max(
                    0.0,
                    min(1.0, (get_settings().QUANTUM_RELEVANCE_THRESHOLD or 0.0)),
                )
                kept_indices = [
                    i
                    for i in range(len(result.items))
                    if (relevance_list[i].get("total_score") or -1.0) >= total_threshold
                ]
                kept_set = set(kept_indices)
                llm_rejected = [
                    result.items[i] for i in range(len(result.items)) if i not in kept_set
                ]
                if llm_rejected and theme_id_uuid:
                    await record_rejected_quanta_candidates(
                        db,
                        theme_id=theme_id_uuid,
                        items=llm_rejected,
                    )
                items_to_save = [result.items[i] for i in kept_indices]
                relevance_by_index = {new_i: relevance_list[kept_indices[new_i]] for new_i in range(len(kept_indices))}
                result.items = items_to_save
                result.total_returned = len(items_to_save)
            except Exception as e:
                logger.warning("collect-by-theme: ошибка оценки релевантности квантов (LLM), сохраняем без opinion_score: %s", e)

        # Перевод только квантов, прошедших обе проверки (embedding + total_score)
        translations_by_index: dict[int, dict] = {}
        if items_to_save and settings.QUANTA_TRANSLATION_METHOD.strip().lower() == "translator":
            translation_service = get_translation_service(request)
            try:
                translations_by_index, cost = await translation_service.translate_quanta_create_items(
                    items_to_save,
                    target_lang=primary_language,
                    billing_session=db,
                    billing_theme_id=theme_id_uuid,
                    titles_only=True,
                )
                logger.info(
                    "collect-by-theme: перевод через %s, входящих символов=%s",
                    settings.TRANSLATOR,
                    cost.input_characters,
                )
            except Exception as e:
                logger.warning("collect-by-theme: ошибка перевода квантов (translator), сохраняем без переводов: %s", e)
        elif items_to_save:
            batch_count = get_translate_batch_count(
                items_to_save,
                primary_language,
                limit=settings.QUANTA_TRANSLATION_LIMIT,
            )
            translate_timeout_s = max(1, batch_count) * SECONDS_PER_TRANSLATE_BATCH
            try:
                translations_by_index = await asyncio.wait_for(
                    translate_quanta_create_items(
                        items_to_save,
                        primary_language,
                        llm_service,
                        prompt_service,
                        limit=settings.QUANTA_TRANSLATION_LIMIT,
                        billing_session=db,
                        billing_theme_id=theme_id_uuid,
                        titles_only=True,
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

        created_quanta = await save_quanta_from_search(
            db,
            items_to_save,
            run_id=run_id_uuid,
            translations_by_index=translations_by_index,
            relevance_by_index=relevance_by_index,
        )

        # Привязка эмбеддингов к квантам по creation_id (в attrs), а не по индексу — чтобы порядок не перепутался при пропусках в save_quanta_from_search
        if result.items_embedding_data and created_quanta and theme_id_uuid:
            model_name = (settings.EMBEDDING_MODEL or "").strip() or "text-embedding-3-small"
            dims = settings.EMBEDDING_DIMENSIONS or 1536
            creation_id_to_quantum = {
                (q.attrs or {}).get("creation_id"): q
                for q in created_quanta
                if (q.attrs or {}).get("creation_id")
            }
            for ed in result.items_embedding_data:
                if not isinstance(ed, dict):
                    continue
                creation_id = ed.get("creation_id")
                quantum = creation_id_to_quantum.get(creation_id) if creation_id else None
                if quantum is None:
                    continue
                vector = ed.get("vector")
                text_hash = ed.get("text_hash")
                if not vector or not isinstance(vector, list) or text_hash is None:
                    continue
                existing = await db.execute(
                    select(Embedding).where(
                        Embedding.theme_id == theme_id_uuid,
                        Embedding.object_type == "quantum",
                        Embedding.object_id == quantum.id,
                        Embedding.embedding_kind == "relevance",
                        Embedding.model == literal(model_name),
                    ).limit(1)
                )
                row = existing.scalar_one_or_none()
                if row:
                    row.embedding = vector
                    row.text_hash = str(text_hash)
                    row.dims = dims
                    row.updated_at = datetime.now(timezone.utc)
                    db.add(row)
                else:
                    db.add(
                        Embedding(
                            theme_id=theme_id_uuid,
                            object_type="quantum",
                            object_id=quantum.id,
                            embedding_kind="relevance",
                            model=model_name,
                            dims=dims,
                            embedding=vector,
                            text_hash=str(text_hash),
                        )
                    )
            await db.flush()

            # Удаляем временный creation_id из attrs в БД (он был нужен только для привязки вектора к кванту в рамках этого запроса)
            for q in created_quanta:
                attrs = q.attrs or {}
                if "creation_id" in attrs:
                    new_attrs = {k: v for k, v in attrs.items() if k != "creation_id"}
                    q.attrs = new_attrs
                    db.add(q)
            await db.flush()
    if result.warnings:
        for w in result.warnings:
            logger.warning("collect-by-theme: %s", w)
    return result
