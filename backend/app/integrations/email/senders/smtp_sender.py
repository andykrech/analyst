"""
Отправка email через SMTP (aiosmtplib), в т.ч. Mailpit.
"""
import logging
from email.message import EmailMessage
from email.utils import formataddr

import aiosmtplib

from app.core.config import Settings
from app.integrations.email.ports import EmailSender

logger = logging.getLogger(__name__)

SMTP_TIMEOUT = 10


class SMTPEmailSender(EmailSender):
    """Отправка писем через SMTP (Mailpit, реальный SMTP и т.д.)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send_email(self, to: str, subject: str, text: str) -> str | None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = formataddr(
            (self._settings.EMAIL_FROM_NAME or None, self._settings.EMAIL_FROM)
        )
        msg["To"] = to
        msg.set_content(text, subtype="plain", charset="utf-8")

        host = self._settings.SMTP_HOST
        port = self._settings.SMTP_PORT
        use_tls = self._settings.SMTP_USE_TLS
        starttls = self._settings.SMTP_STARTTLS
        username = self._settings.SMTP_USERNAME or None
        password = self._settings.SMTP_PASSWORD or None

        try:
            # start_tls=False для Mailpit (не поддерживает STARTTLS); True — автоапгрейд при поддержке сервером
            async with aiosmtplib.SMTP(
                hostname=host,
                port=port,
                use_tls=use_tls,
                start_tls=starttls,
                timeout=SMTP_TIMEOUT,
            ) as smtp:
                if username and password:
                    await smtp.login(username, password)
                await smtp.send_message(
                    msg,
                    sender=self._settings.EMAIL_FROM,
                    recipients=[to],
                )
            logger.info(
                "Email sent via SMTP to=%s subject=%s",
                to,
                subject,
            )
            # SMTP/Mailpit обычно не возвращает message_id в ответе; можно сгенерировать локально при желании
            return None
        except Exception as e:
            logger.exception(
                "SMTP send failed to=%s subject=%s: %s",
                to,
                subject,
                str(e),
            )
            raise
