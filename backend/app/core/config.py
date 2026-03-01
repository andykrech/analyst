"""
Конфигурация приложения из переменных окружения (.env).
"""
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from pydantic import SecretStr

# Загружаем .env из корня backend
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)


def _str(key: str, default: str | None = None) -> str:
    value = os.getenv(key)
    if value is not None:
        return value.strip()
    if default is not None:
        return default
    return ""


def _int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _bool(key: str, default: bool) -> bool:
    raw = os.getenv(key, "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


def _float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _decimal(key: str, default: Decimal | float | int) -> Decimal:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return Decimal(str(default))
    try:
        return Decimal(raw.strip())
    except Exception:
        return Decimal(str(default))


@dataclass(frozen=True)
class ProviderPricing:
    """Тариф провайдера: стоимость за 1M токенов."""

    currency: str
    prompt_per_1m: Decimal
    completion_per_1m: Decimal
    unit: str = "per_1m"


@dataclass
class ProviderConfig:
    """Конфигурация LLM-провайдера."""

    provider: str
    api_key: SecretStr
    base_url: str
    model: str
    timeout_s: int
    pricing: ProviderPricing


class Settings:
    """Настройки приложения."""

    # Email provider: "smtp" | "console" (в будущем можно добавить "sendgrid", "ses" и т.д.)
    EMAIL_PROVIDER: str = _str("EMAIL_PROVIDER", "smtp")

    # Отправитель писем
    EMAIL_FROM: str = _str("EMAIL_FROM", "no-reply@local")
    EMAIL_FROM_NAME: str = _str("EMAIL_FROM_NAME", "")

    # SMTP (для Mailpit или другого SMTP)
    SMTP_HOST: str = _str("SMTP_HOST", "localhost")
    SMTP_PORT: int = _int("SMTP_PORT", 1025)
    SMTP_USERNAME: str = _str("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = _str("SMTP_PASSWORD", "")
    SMTP_USE_TLS: bool = _bool("SMTP_USE_TLS", False)
    SMTP_STARTTLS: bool = _bool("SMTP_STARTTLS", False)

    # Frontend (для ссылок в письмах)
    FRONTEND_BASE_URL: str = _str("FRONTEND_BASE_URL", "http://localhost:5173")

    # JWT для access token при входе
    JWT_SECRET: str = _str("JWT_SECRET", "change-me-in-production")
    JWT_ALGORITHM: str = _str("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = _int("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 7)  # 7 дней

    # LLM: провайдер по умолчанию
    LLM_DEFAULT_PROVIDER: str = _str("LLM_DEFAULT_PROVIDER", "deepseek")

    # DeepSeek
    DEEPSEEK_API_KEY: SecretStr = SecretStr(_str("DEEPSEEK_API_KEY", "dev-deepseek-api-key-change-me"))
    DEEPSEEK_BASE_URL: str = _str("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = _str("DEEPSEEK_MODEL", "deepseek-chat")
    DEEPSEEK_TIMEOUT_S: int = _int("DEEPSEEK_TIMEOUT_S", 60)
    DEEPSEEK_PRICE_PROMPT_PER_1M: Decimal = _decimal("DEEPSEEK_PRICE_PROMPT_PER_1M", 0)
    DEEPSEEK_PRICE_COMPLETION_PER_1M: Decimal = _decimal("DEEPSEEK_PRICE_COMPLETION_PER_1M", 0)
    DEEPSEEK_CURRENCY: str = _str("DEEPSEEK_CURRENCY", "USD")

    # Search: retriever'ы по умолчанию, лимиты (сейчас — OpenAlex публикации).
    # Лимит OpenAlex из env (для теста мог быть SEARCH_MAX_RESULTS_OPENALEX=2 — уберите из .env).
    SEARCH_DEFAULT_RETRIEVERS: list[str] = ["openalex"]
    SEARCH_MAX_RESULTS_PER_RETRIEVER: dict[str, int] = {"openalex": _int("SEARCH_MAX_RESULTS_OPENALEX", 50)}
    SEARCH_DEFAULT_TIME_WINDOW_DAYS: int = _int("SEARCH_DEFAULT_TIME_WINDOW_DAYS", 7)
    SEARCH_DEFAULT_TARGET_LINKS: int = _int("SEARCH_DEFAULT_TARGET_LINKS", 50)

    # Перевод квантов: метод "translator" (DeepL и др.) | "llm" (текущий ИИ)
    QUANTA_TRANSLATION_METHOD: str = _str("QUANTA_TRANSLATION_METHOD", "translator")
    # Макс. число квантов для перевода: 0 = все, >0 = только первые N (для отладки и экономии лимитов)
    QUANTA_TRANSLATION_LIMIT: int = _int("QUANTA_TRANSLATION_LIMIT", 0)
    # Используемый переводчик (при QUANTA_TRANSLATION_METHOD=translator): deepl, ...
    TRANSLATOR: str = _str("TRANSLATOR", "deepl")
    # DeepL API (REST)
    DEEPL_API_KEY: SecretStr = SecretStr(_str("DEEPL_API_KEY", ""))
    # Yandex Cloud Translate API (REST); folder — тот же YANDEX_FOLDER_ID
    YANDEX_API_KEY_TRANSLATE: SecretStr = SecretStr(_str("YANDEX_API_KEY_TRANSLATE", ""))

    # OpenAlex API (публикации)
    OPENALEX_API_KEY: str = _str("OPENALEX_API_KEY", "")

    # Yandex Search API v2 (gRPC)
    YANDEX_API_KEY: str = _str("YANDEX_API_KEY", "changeme")
    YANDEX_FOLDER_ID: str = _str("YANDEX_FOLDER_ID", "changeme")
    YANDEX_SEARCH_ENDPOINT: str = _str("YANDEX_SEARCH_ENDPOINT", "searchapi.api.cloud.yandex.net:443")
    YANDEX_OPERATION_ENDPOINT: str = _str("YANDEX_OPERATION_ENDPOINT", "operation.api.cloud.yandex.net:443")
    YANDEX_SEARCH_REGION: str = _str("YANDEX_SEARCH_REGION", "225")
    YANDEX_SEARCH_TIMEOUT_SECONDS: int = _int("YANDEX_SEARCH_TIMEOUT_SECONDS", 10)
    YANDEX_OPERATION_POLL_ATTEMPTS: int = _int("YANDEX_OPERATION_POLL_ATTEMPTS", 10)
    YANDEX_OPERATION_POLL_INTERVAL_SECONDS: float = _float("YANDEX_OPERATION_POLL_INTERVAL_SECONDS", 0.5)

    # Туннель (прокси) для части интеграций (например OpenAI Embeddings).
    # URL в формате socks5://[user:password@]host:port или http://...; пусто — без прокси.
    TUNNEL_PROXY_URL: str = _str("TUNNEL_PROXY_URL", "")

    # OpenAI (эмбеддинги и др.); ключ — заглушка, подставить свой в .env
    OPENAI_API_KEY: SecretStr = SecretStr(_str("OPENAI_API_KEY", ""))
    OPENAI_BASE_URL: str = _str("OPENAI_BASE_URL", "https://api.openai.com")
    OPENAI_EMBEDDING_TIMEOUT_S: int = _int("OPENAI_EMBEDDING_TIMEOUT_S", 30)
    OPENAI_EMBEDDING_MAX_RETRIES: int = _int("OPENAI_EMBEDDING_MAX_RETRIES", 3)
    OPENAI_EMBEDDING_RETRY_DELAY_S: float = _float("OPENAI_EMBEDDING_RETRY_DELAY_S", 2.0)

    # Эмбеддинги: провайдер по умолчанию, модель, размерность, стоимость за 1 токен (для оценки)
    EMBEDDING_PROVIDER: str = _str("EMBEDDING_PROVIDER", "openai")
    EMBEDDING_MODEL: str = _str("EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_DIMENSIONS: int = _int("EMBEDDING_DIMENSIONS", 1536)
    EMBEDDING_COST_PER_TOKEN: Decimal = _decimal("EMBEDDING_COST_PER_TOKEN", 0)

    # Двухуровневая фильтрация квантов:
    # 1) По векторам: rank_score >= EMBEDDING_QUANTUM_RELEVANCE_THRESHOLD (-1..1, косинус); ниже — не запрашиваем ИИ и не сохраняем.
    EMBEDDING_QUANTUM_RELEVANCE_THRESHOLD: float = _float("EMBEDDING_QUANTUM_RELEVANCE_THRESHOLD", -1.0)
    # 2) По итогу ИИ: total_score >= QUANTUM_RELEVANCE_THRESHOLD (0..1); ниже — не сохраняем.
    QUANTUM_RELEVANCE_THRESHOLD: float = _float("QUANTUM_RELEVANCE_THRESHOLD", 0.0)

    # Промпты: провайдер (file | db), директория, алиасы, TTL кеша
    PROMPT_PROVIDER: str = _str("PROMPT_PROVIDER", "file")
    PROMPT_FILES_DIR: str = _str("PROMPT_FILES_DIR", "app/prompts/prompts")
    PROMPT_ALIASES_FILE: str = _str("PROMPT_ALIASES_FILE", "app/prompts/aliases.yml")
    PROMPT_CACHE_TTL_S: int = _int("PROMPT_CACHE_TTL_S", 0)

    @property
    def llm_registry(self) -> dict[str, ProviderConfig]:
        """Реестр конфигураций LLM-провайдеров (ключ — имя провайдера)."""
        return {
            "deepseek": ProviderConfig(
                provider="deepseek",
                api_key=self.DEEPSEEK_API_KEY,
                base_url=self.DEEPSEEK_BASE_URL.rstrip("/"),
                model=self.DEEPSEEK_MODEL,
                timeout_s=self.DEEPSEEK_TIMEOUT_S,
                pricing=ProviderPricing(
                    currency=self.DEEPSEEK_CURRENCY,
                    prompt_per_1m=self.DEEPSEEK_PRICE_PROMPT_PER_1M,
                    completion_per_1m=self.DEEPSEEK_PRICE_COMPLETION_PER_1M,
                    unit="per_1m",
                ),
            ),
        }


# Глобальный экземпляр конфига (инициализируется при первом импорте)
_settings: Settings | None = None


def get_settings() -> Settings:
    """Возвращает экземпляр настроек (singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
