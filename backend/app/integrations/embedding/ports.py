"""
Порт (интерфейс) провайдеров эмбеддингов.
Верхний слой (EmbeddingService) вызывает выбранный провайдер по имени.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class EmbeddingCost:
    """Оценка стоимости эмбеддинга: токены и итоговая сумма."""

    total_tokens: int
    """Число токенов (из ответа провайдера или оценка)."""
    total_cost: Decimal
    """Итоговая стоимость (из провайдера или tokens * cost_per_token)."""


@dataclass
class EmbeddingResult:
    """Результат эмбеддинга: вектор и стоимость."""

    vector: list[float]
    """Вектор эмбеддинга."""
    cost: EmbeddingCost
    """Стоимость (токены + сумма)."""


class EmbeddingProviderPort(Protocol):
    """Абстракция провайдера эмбеддингов."""

    @property
    def name(self) -> str:
        """Имя провайдера (например 'openai')."""
        ...

    async def embed(
        self,
        text: str,
        model: str,
        dimensions: int,
        cost_per_token: Decimal,
    ) -> EmbeddingResult:
        """
        Построить эмбеддинг для текста.

        Args:
            text: исходный текст.
            model: название модели (например text-embedding-3-small).
            dimensions: размерность вектора.
            cost_per_token: стоимость за 1 токен (для расчёта, если провайдер не вернул usage).

        Returns:
            EmbeddingResult с вектором и стоимостью.
        """
        ...
