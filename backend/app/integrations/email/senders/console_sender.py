"""
Fallback: печать письма в лог/консоль (без реальной отправки).
"""
import logging

from app.integrations.email.ports import EmailSender

logger = logging.getLogger(__name__)


class ConsoleEmailSender(EmailSender):
    """Отправка «в консоль» — только логирование."""

    async def send_email(self, to: str, subject: str, text: str) -> str | None:
        logger.info(
            "[ConsoleEmail] to=%s subject=%s\n---\n%s\n---",
            to,
            subject,
            text,
        )
        return None
