"""
Фабрика LLM-провайдеров по имени. Провайдер получает настройки только из Settings.
"""
import httpx

from app.core.config import Settings
from app.integrations.llm.ports import LLMProviderPort
from app.integrations.llm.providers.deepseek import DeepSeekProvider


def get_provider(
    provider_name: str,
    settings: Settings,
    http_client: httpx.AsyncClient,
) -> LLMProviderPort:
    """
    Вернуть экземпляр провайдера по имени.

    Поддерживается: "deepseek".
    Иначе — ValueError.
    """
    name = (provider_name or "").strip().lower()
    if name == "deepseek":
        config = settings.llm_registry["deepseek"]
        return DeepSeekProvider(config, http_client)
    raise ValueError(f"Unknown LLM provider: {provider_name}")
