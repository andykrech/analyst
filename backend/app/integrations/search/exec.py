"""
SearchExecutor: выполняет план поиска, применяет MUST/EXCLUDE, TimeSlice, дедуп, обрезку.

Работает с квантами (QuantumCreate). TimeSlice — фильтр по date_at.
"""
from app.integrations.search.ports import RetrieverContext, RetrieverPort
from app.integrations.search.schemas import (
    QuantumCollectResult,
    QueryStep,
    SearchPlan,
    StepResult,
    TimeSlice,
)
from app.integrations.search.utils import (
    dedup_quanta,
    filter_by_exclude_quanta,
    filter_by_must_have_quanta,
)
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
    from app.integrations.search.utils import _quantum_dedup_key
    return (q.theme_id, _quantum_dedup_key(q))


class SearchExecutor:
    """
    Исполнитель плана поиска: вызывает retriever'ы (кванты),
    применяет MUST/EXCLUDE, TimeSlice по date_at, дедуплицирует, обрезает.
    """

    def __init__(
        self,
        registry: dict[str, RetrieverPort],
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
    ) -> QuantumCollectResult:
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

            must_block = step.query_model.must
            exclude_block = step.query_model.exclude

            if must_block.terms:
                filtered = filter_by_must_have_quanta(
                    raw_items,
                    must_block.terms,
                    mode=must_block.mode,
                )
            else:
                filtered = list(raw_items)

            filtered = filter_by_exclude_quanta(filtered, exclude_block.terms)

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
        total_found = len(all_items)
        final_items = all_items[:global_target_links]
        total_returned = len(final_items)

        return QuantumCollectResult(
            items=final_items,
            plan=plan,
            step_results=step_results,
            total_found=total_found,
            total_returned=total_returned,
        )
