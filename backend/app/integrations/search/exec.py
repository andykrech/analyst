"""
SearchExecutor: выполняет план поиска, нормализует URL, дедуплицирует, обрезает.

keywords, must_have, exclude передаются в retriever как параметры поиска;
фильтрация результатов — ответственность retriever'а (поисковой системы).
"""
from app.integrations.search.ports import LinkRetrieverPort, RetrieverContext
from app.integrations.search.schemas import (
    LinkCandidate,
    LinkCollectResult,
    QueryStep,
    SearchPlan,
    SearchQuery,
    StepResult,
)
from app.integrations.search.utils import dedup_by_hash, normalize_url, url_hash


class SearchExecutor:
    """
    Исполнитель плана поиска: вызывает retriever'ы, нормализует URL,
    дедуплицирует, обрезает до target_links.
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
        query: SearchQuery,
        ctx: RetrieverContext,
    ) -> LinkCollectResult:
        all_items: list[LinkCandidate] = []
        step_results: list[StepResult] = []
        seen_hashes: set[str] = set()
        target_links = query.target_links

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

            retriever = self._registry.get(step.retriever)
            if retriever is None:
                step_results.append(
                    StepResult(
                        step_id=step.step_id,
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

            # Дедуп по url_hash между шагами
            step_items: list[LinkCandidate] = []
            for item in normalized:
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
                    status="done",
                    found=found_count,
                    returned=returned_count,
                )
            )

        # Финальная дедупликация (на случай пересечений)
        all_items = dedup_by_hash(all_items)

        # Обрезка до target_links
        total_found = len(all_items)
        final_items = all_items[:target_links]
        total_returned = len(final_items)

        return LinkCollectResult(
            items=final_items,
            plan=plan,
            step_results=step_results,
            total_found=total_found,
            total_returned=total_returned,
        )
