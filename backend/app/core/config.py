"""
Конфигурация приложения из переменных окружения (.env).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

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


# Глобальный экземпляр конфига (инициализируется при первом импорте)
_settings: Settings | None = None


def get_settings() -> Settings:
    """Возвращает экземпляр настроек (singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
