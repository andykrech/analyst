"""
SearchPlanner: строит план поиска по query и настройкам.
"""
from app.core.config import Settings
from app.integrations.search.schemas import QueryStep, SearchPlan, SearchQuery


class SearchPlanner:
    """
    Планировщик поиска: определяет retriever'ы и создаёт шаги плана.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build_plan(
        self,
        query: SearchQuery,
        mode: str = "discovery",
    ) -> SearchPlan:
        """
        Построить план поиска.

        Retriever'ы: query.enabled_retrievers или settings.SEARCH_DEFAULT_RETRIEVERS.
        max_results: settings.SEARCH_MAX_RESULTS_PER_RETRIEVER.get(name, default).
        """
        retrievers = (
            query.enabled_retrievers
            if query.enabled_retrievers is not None and len(query.enabled_retrievers) > 0
            else self._settings.SEARCH_DEFAULT_RETRIEVERS
        )
        max_per = self._settings.SEARCH_MAX_RESULTS_PER_RETRIEVER
        default_max = self._settings.SEARCH_DEFAULT_TARGET_LINKS

        steps: list[QueryStep] = []
        for idx, retriever_name in enumerate(retrievers):
            max_results = max_per.get(retriever_name, default_max)
            step_id = f"step_{idx}_{retriever_name}"
            steps.append(
                QueryStep(
                    step_id=step_id,
                    retriever=retriever_name,
                    query=query,
                    max_results=max_results,
                )
            )

        return SearchPlan(
            plan_version=1,
            mode=mode if mode in ("discovery", "monitoring") else "discovery",
            steps=steps,
        )
