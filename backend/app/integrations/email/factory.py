"""
Фабрика выбора реализации EmailSender по EMAIL_PROVIDER из env.
"""
from app.core.config import Settings, get_settings
from app.integrations.email.ports import EmailSender
from app.integrations.email.senders.console_sender import ConsoleEmailSender
from app.integrations.email.senders.smtp_sender import SMTPEmailSender


def get_email_sender(settings: Settings | None = None) -> EmailSender:
    """
    Возвращает экземпляр EmailSender в зависимости от EMAIL_PROVIDER.

    - "smtp" (по умолчанию) — SMTP (Mailpit и др.)
    - "console" — вывод в лог/консоль

    Для добавления нового провайдера: реализовать класс в senders/
    и добавить ветку сюда.
    """
    if settings is None:
        settings = get_settings()
    provider = (settings.EMAIL_PROVIDER or "smtp").strip().lower()
    if provider == "console":
        return ConsoleEmailSender()
    if provider == "smtp":
        return SMTPEmailSender(settings)
    # Неизвестный провайдер — fallback на console
    return ConsoleEmailSender()
