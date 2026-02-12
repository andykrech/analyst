"""
SearchExecutor: выполняет план поиска, нормализует URL, дедуплицирует, обрезает.

TimeSlice применяется как фильтр по published_at в верхнем слое (Executor).
Retriever не знает про время — он получает только структурный query_model.
"""
from app.integrations.search.ports import LinkRetrieverPort, RetrieverContext
from app.integrations.search.schemas import (
    LinkCandidate,
    LinkCollectResult,
    QueryStep,
    SearchPlan,
    StepResult,
    TimeSlice,
)
from app.integrations.search.utils import dedup_by_hash, filter_by_exclude, normalize_url, url_hash


def _apply_time_slice(
    items: list[LinkCandidate],
    time_slice: TimeSlice,
) -> list[LinkCandidate]:
    """
    Фильтр по published_at: оставить только в [published_from, published_to].
    Если published_at is None — не отбрасывать (MVP), добавить date_unknown в meta.
    """
    result: list[LinkCandidate] = []
    for item in items:
        if item.published_at is not None:
            if time_slice.published_from <= item.published_at <= time_slice.published_to:
                result.append(item)
            # иначе отбрасываем
        else:
            # MVP: не отбрасываем, помечаем
            meta = dict(item.provider_meta)
            meta["date_unknown"] = True
            result.append(
                LinkCandidate(
                    url=item.url,
                    title=item.title,
                    snippet=item.snippet,
                    published_at=None,
                    provider=item.provider,
                    rank=item.rank,
                    provider_meta=meta,
                    normalized_url=item.normalized_url,
                    url_hash=item.url_hash,
                )
            )
    return result


class SearchExecutor:
    """
    Исполнитель плана поиска: вызывает retriever'ы, нормализует URL,
    применяет must_have, exclude, TimeSlice, дедуплицирует, обрезает.
    """

    def __init__(
        self,
        registry: dict[str, LinkRetrieverPort],
        settings,
    ) -> None:
        self._registry = registry
        self._settings = settings

    async def execute(
        self,
        plan: SearchPlan,
        time_slice: TimeSlice | None,
        global_target_links: int,
        ctx: RetrieverContext,
    ) -> LinkCollectResult:
        all_items: list[LinkCandidate] = []
        step_results: list[StepResult] = []
        seen_hashes: set[str] = set()

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

            # Досрочный выход при достижении лимита
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
                raw_items = await retriever.retrieve(step, ctx)
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

            # Нормализация: заполнить normalized_url и url_hash
            normalized: list[LinkCandidate] = []
            for item in raw_items:
                norm_url = normalize_url(item.url)
                h = url_hash(norm_url)
                normalized.append(
                    LinkCandidate(
                        url=item.url,
                        title=item.title,
                        snippet=item.snippet,
                        published_at=item.published_at,
                        provider=item.provider,
                        rank=item.rank,
                        provider_meta=item.provider_meta,
                        normalized_url=norm_url,
                        url_hash=h,
                    )
                )

            # Локальные фильтры шага: must/exclude из query_model
            must_block = step.query_model.must
            exclude_block = step.query_model.exclude

            # must: ALL / ANY
            if must_block.terms:
                if must_block.mode == "ALL":
                    # ALL: оставить только элементы, содержащие все фразы
                    from app.integrations.search.utils import filter_by_must_have

                    filtered = filter_by_must_have(normalized, must_block.terms)
                else:
                    # ANY: оставить элементы, содержащие хотя бы одну фразу
                    from app.integrations.search.utils import _text_for_filtering

                    tmp: list[LinkCandidate] = []
                    for item in normalized:
                        text = _text_for_filtering(item)
                        if any(term.lower() in text for term in must_block.terms if term):
                            tmp.append(item)
                    filtered = tmp
            else:
                filtered = list(normalized)

            # exclude: убрать элементы, содержащие любую фразу
            filtered = filter_by_exclude(filtered, exclude_block.terms)

            # TimeSlice: фильтр по published_at (только в Executor)
            if time_slice is not None:
                filtered = _apply_time_slice(filtered, time_slice)

            # Дедуп по url_hash между шагами
            step_items: list[LinkCandidate] = []
            for item in filtered:
                if item.url_hash and item.url_hash in seen_hashes:
                    continue
                if item.url_hash:
                    seen_hashes.add(item.url_hash)
                step_items.append(item)

            returned_count = len(step_items)
            found_count = len(normalized)
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

            # Досрочный выход при достижении лимита
            if len(all_items) >= global_target_links:
                # Оставшиеся шаги помечаем skipped
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

        # Финальная дедупликация
        all_items = dedup_by_hash(all_items)

        # Обрезка до global_target_links
        total_found = len(all_items)
        final_items = all_items[:global_target_links]
        total_returned = len(final_items)

        return LinkCollectResult(
            items=final_items,
            plan=plan,
            step_results=step_results,
            total_found=total_found,
            total_returned=total_returned,
        )
