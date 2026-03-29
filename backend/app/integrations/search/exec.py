"""
SearchExecutor: выполняет план поиска, применяет TimeSlice, дедуп, обрезку.

Работает с квантами (QuantumCreate). TimeSlice — фильтр по date_at.
После дедупа: эмбеддинги квантов, сходство с темой, фильтр по порогу релевантности, rank_score.

Чтобы не перепутать порядок векторов и квантов при сохранении в БД, каждому кванту
присваивается временный creation_id в attrs; он же кладётся в items_embedding_data.
В роутере привязка эмбеддинга к кванту идёт по creation_id, после чего creation_id
удаляется из attrs в БД.
"""
import hashlib
import logging
import uuid as uuid_module
from typing import Any

from app.integrations.search.ports import (
    RetrieverContext,
    RetrieverPort,
    SearchBillingUsageLine,
)
from app.integrations.search.schemas import (
    QuantumCollectResult,
    QueryStep,
    SearchPlan,
    StepResult,
    TimeSlice,
)
from app.integrations.search.utils import _quantum_dedup_key, dedup_quanta
from app.modules.quanta.crud import record_rejected_quanta_candidates
from app.modules.quanta.schemas import QuantumCreate


def _apply_time_slice_quanta(
    items: list[QuantumCreate],
    time_slice: TimeSlice,
) -> list[QuantumCreate]:
    """
    Фильтр по date_at: оставить только в [published_from, published_to].
    Если date_at is None — не отбрасывать (MVP).
    """
    result: list[QuantumCreate] = []
    for q in items:
        if q.date_at is None:
            result.append(q)
            continue
        if time_slice.published_from <= q.date_at <= time_slice.published_to:
            result.append(q)
    return result


def _quantum_dedup_key_for_seen(q: QuantumCreate) -> tuple[str, str]:
    """Ключ для seen: (theme_id, dedup_key)."""
    return (q.theme_id, _quantum_dedup_key(q))


def _drop_already_stored_or_rejected_quanta(
    items: list[QuantumCreate],
    ctx: RetrieverContext,
) -> list[QuantumCreate]:
    """После dedup: убрать уже сохранённые кванты и ранее отклонённых кандидатов."""
    existing = ctx.existing_theme_dedup_keys
    rejected = ctx.rejected_quanta_candidate_keys
    if not existing and not rejected:
        return items
    out: list[QuantumCreate] = []
    for q in items:
        dk = _quantum_dedup_key(q)
        if dk in existing:
            continue
        if (str(q.entity_kind), dk) in rejected:
            continue
        out.append(q)
    return out


def _quantum_description_for_embedding(q: QuantumCreate) -> str:
    """Строка для эмбеддинга кванта: Title + Summary text."""
    title = (q.title or "").strip()
    summary = (q.summary_text or "").strip()
    return f"Title:\n{title}\n\nSummary text:\n{summary}"


def _description_hash(description: str) -> str:
    """SHA-256 hash строки в hex."""
    return hashlib.sha256(description.encode("utf-8")).hexdigest()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Косинусное сходство; возвращает значение в [-1, 1]."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a <= 0 or norm_b <= 0:
        return 0.0
    return dot / (norm_a * norm_b)


_SEARCH_BILLING_TASK_TYPE = "search_collect"


async def _flush_search_billing(
    *,
    ctx: RetrieverContext,
    billing_lines: list[SearchBillingUsageLine],
    step: QueryStep,
) -> None:
    """Пишет строки биллинга поиска; при жёстком биллинге пробрасывает BillingConfigError."""
    if not billing_lines:
        return
    bs = ctx.billing_service
    session = ctx.billing_session
    theme_id = ctx.billing_theme_id
    if bs is None or session is None or theme_id is None:
        return
    base_extra: dict[str, Any] = {
        "retriever": step.retriever,
        "step_id": str(step.step_id),
        "source_query_id": str(step.source_query_id),
    }
    if ctx.request_id:
        base_extra["request_id"] = ctx.request_id
    if ctx.run_id is not None:
        base_extra["run_id"] = str(ctx.run_id)
    for line in billing_lines:
        merged = {**base_extra, **(line.extra or {})}
        await bs.record_usage(
            session,
            theme_id=theme_id,
            task_type=_SEARCH_BILLING_TASK_TYPE,
            service_type=line.service_type,
            service_impl=line.service_impl,
            quantity=line.quantity,
            quantity_unit_code=line.quantity_unit_code,
            extra=merged,
        )


class SearchExecutor:
    """
    Исполнитель плана поиска: вызывает retriever'ы (кванты),
    применяет MUST/EXCLUDE, TimeSlice по date_at, дедуплицирует, обрезает.
    """

    def __init__(
        self,
        registry: dict[str, RetrieverPort],
        settings: Any,
        embedding_service: Any = None,
    ) -> None:
        self._registry = registry
        self._settings = settings
        self._embedding_service = embedding_service

    async def execute(
        self,
        plan: SearchPlan,
        time_slice: TimeSlice | None,
        global_target_links: int,
        ctx: RetrieverContext,
    ) -> QuantumCollectResult:
        logger = logging.getLogger(__name__)
        logger.info(
            "search/executor: запуск, global_target_links=%s, шагов в плане=%s",
            global_target_links,
            len(plan.steps),
        )
        all_items: list[QuantumCreate] = []
        step_results: list[StepResult] = []
        seen_keys: set[tuple[str, str]] = set()

        for step in plan.steps:
            if not isinstance(step, QueryStep):
                step_results.append(
                    StepResult(
                        step_id=step.step_id,
                        status="skipped",
                        found=0,
                        returned=0,
                        error="Unknown step kind",
                    )
                )
                continue

            if len(all_items) >= global_target_links:
                step_results.append(
                    StepResult(
                        step_id=step.step_id,
                        source_query_id=step.source_query_id,
                        retriever=step.retriever,
                        order_index=step.order_index,
                        status="skipped",
                        found=0,
                        returned=0,
                        error="Target links reached",
                    )
                )
                continue

            retriever = self._registry.get(step.retriever)
            if retriever is None:
                step_results.append(
                    StepResult(
                        step_id=step.step_id,
                        source_query_id=step.source_query_id,
                        retriever=step.retriever,
                        order_index=step.order_index,
                        status="failed",
                        found=0,
                        returned=0,
                        error=f"Retriever '{step.retriever}' not found",
                    )
                )
                continue

            try:
                r_result = await retriever.retrieve(step, ctx)
            except Exception as e:
                step_results.append(
                    StepResult(
                        step_id=step.step_id,
                        source_query_id=step.source_query_id,
                        retriever=step.retriever,
                        order_index=step.order_index,
                        status="failed",
                        found=0,
                        returned=0,
                        error=str(e),
                    )
                )
                continue

            await _flush_search_billing(
                ctx=ctx,
                billing_lines=r_result.billing_lines,
                step=step,
            )

            raw_items = r_result.items
            filtered = list(raw_items)
            if time_slice is not None:
                filtered = _apply_time_slice_quanta(filtered, time_slice)

            step_items: list[QuantumCreate] = []
            for q in filtered:
                key = _quantum_dedup_key_for_seen(q)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                step_items.append(q)

            returned_count = len(step_items)
            found_count = len(raw_items)
            all_items.extend(step_items)

            step_results.append(
                StepResult(
                    step_id=step.step_id,
                    source_query_id=step.source_query_id,
                    retriever=step.retriever,
                    order_index=step.order_index,
                    status="done",
                    found=found_count,
                    returned=returned_count,
                )
            )

            if len(all_items) >= global_target_links:
                remaining = [
                    s
                    for s in plan.steps[plan.steps.index(step) + 1 :]
                    if isinstance(s, QueryStep)
                ]
                for s in remaining:
                    step_results.append(
                        StepResult(
                            step_id=s.step_id,
                            source_query_id=s.source_query_id,
                            retriever=s.retriever,
                            order_index=s.order_index,
                            status="skipped",
                            found=0,
                            returned=0,
                            error="Target links reached",
                        )
                    )
                break

        all_items = dedup_quanta(all_items)
        all_items = _drop_already_stored_or_rejected_quanta(all_items, ctx)
        total_found = len(all_items)
        warnings: list[str] = []
        items_embedding_data: list[dict] | None = None

        theme_vector = ctx.theme_relevance_vector
        if ctx.theme_id is not None and theme_vector is None:
            raise ValueError(
                "Вектор релевантности темы отсутствует. Невозможно оценить релевантность квантов."
            )

        if theme_vector is not None and self._embedding_service is not None and all_items:
            model_name = (getattr(self._settings, "EMBEDDING_MODEL", None) or "").strip() or "text-embedding-3-small"
            embedding_threshold = max(
                -1.0,
                min(1.0, getattr(self._settings, "EMBEDDING_QUANTUM_RELEVANCE_THRESHOLD", -1.0) or -1.0),
            )
            # Кортеж: (квант, вектор, text_hash, rank_score, creation_id) — creation_id для однозначной привязки к эмбеддингу при сохранении в БД
            per_item: list[tuple[QuantumCreate, list[float] | None, str, float, str]] = []
            embed_fail_count = 0
            for q in all_items:
                # Временный id на время запроса: попадёт в attrs кванта и в items_embedding_data, в конце запроса удаляется из attrs в БД
                creation_id = str(uuid_module.uuid4())
                if q.attrs is None:
                    q.attrs = {}
                q.attrs["creation_id"] = creation_id

                desc = _quantum_description_for_embedding(q)
                text_hash = _description_hash(desc)
                vector: list[float] | None = None
                rank_score = 0.0
                try:
                    embed_kw: dict[str, Any] = {}
                    if (
                        ctx.billing_service is not None
                        and ctx.billing_session is not None
                        and ctx.theme_id is not None
                    ):
                        embed_kw = {
                            "billing_session": ctx.billing_session,
                            "billing_theme_id": ctx.theme_id,
                            "billing_task_type": "search_quantum_embedding",
                            "billing_extra": {"context": "search_executor"},
                        }
                    result = await self._embedding_service.embed(desc, **embed_kw)
                    vec = result.get("vector")
                    if vec and isinstance(vec, list):
                        vector = vec
                        sim = _cosine_similarity(vector, theme_vector)
                        rank_score = sim
                except Exception as e:
                    embed_fail_count += 1
                    logger.warning("search/executor: эмбеддинг кванта не удался: %s", e)
                per_item.append((q, vector, text_hash, rank_score, creation_id))

            if embed_fail_count > 0:
                warnings.append(f"Ошибка эмбеддинга для {embed_fail_count} квантов; для них установлен rank_score=0.")

            for q, _v, _h, score, _cid in per_item:
                q.rank_score = score
            embedding_rejected = [t[0] for t in per_item if t[3] < embedding_threshold]
            if (
                embedding_rejected
                and ctx.billing_session is not None
                and ctx.billing_theme_id is not None
            ):
                await record_rejected_quanta_candidates(
                    ctx.billing_session,
                    theme_id=ctx.billing_theme_id,
                    items=embedding_rejected,
                )
            filtered_per_item = [t for t in per_item if t[3] >= embedding_threshold]
            final_per_item = filtered_per_item[:global_target_links]
            final_items = [t[0] for t in final_per_item]
            # В каждом элементе — creation_id, чтобы в роутере привязать эмбеддинг к кванту по id, а не по индексу (порядок created_quanta может не совпадать с items из‑за пропусков при сохранении)
            items_embedding_data = [
                {"vector": t[1], "text_hash": t[2], "creation_id": t[4]}
                for t in final_per_item
            ]
            total_returned = len(final_items)
            total_found = len(filtered_per_item)
        else:
            final_items = all_items[:global_target_links]
            total_returned = len(final_items)

        logger.info(
            "search/executor: итог total_found=%s, total_returned=%s, len(final_items)=%s",
            total_found,
            total_returned,
            len(final_items),
        )

        return QuantumCollectResult(
            items=final_items,
            plan=plan,
            step_results=step_results,
            total_found=total_found,
            total_returned=total_returned,
            items_embedding_data=items_embedding_data if items_embedding_data else None,
            warnings=warnings if warnings else None,
        )
