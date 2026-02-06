"""
Фабрика провайдера промптов по настройкам.
"""
from app.core.config import Settings
from app.integrations.prompts.ports import PromptProviderPort
from app.integrations.prompts.providers.file_provider import FilePromptProvider


def get_prompt_provider(settings: Settings) -> PromptProviderPort:
    """
    Вернуть экземпляр провайдера промптов по PROMPT_PROVIDER.

    Поддерживается: "file". Иначе — ValueError.
    """
    provider = (settings.PROMPT_PROVIDER or "file").strip().lower()
    if provider == "file":
        return FilePromptProvider(settings)
    raise ValueError(f"Unsupported prompt provider: {settings.PROMPT_PROVIDER!r}")
