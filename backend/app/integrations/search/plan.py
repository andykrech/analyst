"""
SearchPlanner: строит план поиска.

theme_search_queries — источник истины для планирования поиска.
Planner не использует keywords темы, не использует TimeSlice.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.search.schemas import (
    ExcludeBlock,
    KeywordsBlock,
    KeywordGroup,
    MustBlock,
    QueryModel,
    QueryStep,
    SearchPlan,
    SearchQuery,
)
from app.modules.theme.model import ThemeSearchQuery


class SearchPlanner:
    """
    Планировщик поиска: читает theme_search_queries и создаёт шаги плана.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def build_plan_for_theme(
        self,
        session: AsyncSession,
        theme_id: UUID,
        mode: str = "default",
        languages: list[str] | None = None,
    ) -> SearchPlan:
        """
        Построить план поиска из theme_search_queries.

        SELECT FROM theme_search_queries
        WHERE theme_id = :theme_id AND is_enabled = true
        ORDER BY order_index ASC

        Для каждой записи и каждого retriever'а создаётся шаг для каждого языка из languages.
        Если languages пустой/None — один шаг без языка (retriever использует ctx.language).
        max_results: settings.SEARCH_MAX_RESULTS_PER_RETRIEVER, ограниченный target_links записи.
        """
        result = await session.execute(
            select(ThemeSearchQuery)
            .where(
                ThemeSearchQuery.theme_id == theme_id,
                ThemeSearchQuery.is_enabled == True,
            )
            .order_by(ThemeSearchQuery.order_index.asc())
        )
        rows = result.scalars().all()

        default_retrievers = self._settings.SEARCH_DEFAULT_RETRIEVERS
        max_per_retriever = self._settings.SEARCH_MAX_RESULTS_PER_RETRIEVER
        default_max = self._settings.SEARCH_DEFAULT_TARGET_LINKS

        # Один «язык» = один шаг; при отсутствии languages — один шаг с language=None
        lang_list: list[str | None] = [None]
        if languages:
            lang_list = [lang for lang in languages if isinstance(lang, str) and lang.strip()] or [None]

        steps: list[QueryStep] = []
        for row in rows:
            if not row.query_model:
                continue

            retrievers = (
                row.enabled_retrievers
                if row.enabled_retrievers
                else default_retrievers
            )

            for retriever_name in retrievers:
                base_max = max_per_retriever.get(retriever_name, default_max)
                max_results = (
                    min(base_max, row.target_links)
                    if row.target_links is not None
                    else base_max
                )
                query_model = QueryModel.model_validate(row.query_model)

                for lang in lang_list:
                    lang_suffix = lang or "default"
                    step_id = f"q{row.order_index}-{row.id}-{retriever_name}-{lang_suffix}"
                    steps.append(
                        QueryStep(
                            step_id=step_id,
                            retriever=retriever_name,
                            source_query_id=row.id,
                            order_index=row.order_index,
                            query_model=query_model,
                            max_results=max_results,
                            language=lang,
                        )
                    )

        return SearchPlan(
            plan_version=1,
            mode=mode if mode in ("discovery", "monitoring") else "discovery",
            steps=steps,
        )

    def build_plan(
        self,
        query: SearchQuery,
        mode: str = "discovery",
    ) -> SearchPlan:
        """
        Legacy: построить план по SearchQuery (для обратной совместимости).
        """
        retrievers = (
            query.enabled_retrievers
            if query.enabled_retrievers
            else self._settings.SEARCH_DEFAULT_RETRIEVERS
        )
        max_per = self._settings.SEARCH_MAX_RESULTS_PER_RETRIEVER
        default_max = self._settings.SEARCH_DEFAULT_TARGET_LINKS

        steps: list[QueryStep] = []
        # Legacy: строим минимальный QueryModel из SearchQuery.
        # keywords -> одна группа с op=OR,
        # text (если есть и нет keywords) -> один терм.
        if query.keywords:
            base_terms = query.keywords
        elif query.text:
            base_terms = [query.text]
        else:
            base_terms = [" "]

        legacy_query_model = QueryModel(
            keywords=KeywordsBlock(
                groups=[
                    KeywordGroup(
                        op="OR",
                        terms=base_terms,
                    )
                ],
                connectors=[],
            ),
            must=MustBlock(
                mode="ALL",
                terms=query.must_have or [],
            ),
            exclude=ExcludeBlock(
                terms=query.exclude or [],
            ),
        )

        for idx, retriever_name in enumerate(retrievers):
            max_results = max_per.get(retriever_name, default_max)
            step_id = f"legacy_{idx}_{retriever_name}"
            steps.append(
                QueryStep(
                    step_id=step_id,
                    retriever=retriever_name,
                    source_query_id=UUID("00000000-0000-0000-0000-000000000000"),
                    order_index=idx,
                    query_model=legacy_query_model,
                    max_results=max_results,
                    language=None,
                )
            )

        return SearchPlan(
            plan_version=1,
            mode=mode if mode in ("discovery", "monitoring") else "discovery",
            steps=steps,
        )
