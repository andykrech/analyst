"""
Use-cases для email, связанных с аутентификацией.
"""
from app.integrations.email.ports import EmailSender
from app.integrations.email.templates.verify_email import render_verify_email


class AuthEmailService:
    """Сервис отправки писем, связанных с аутентификацией (подтверждение email и т.д.)."""

    def __init__(self, sender: EmailSender) -> None:
        self._sender = sender

    async def send_verification_email(
        self,
        to_email: str,
        verify_link: str,
    ) -> str | None:
        """
        Отправить письмо с ссылкой подтверждения регистрации.

        Args:
            to_email: Email получателя.
            verify_link: Полная ссылка для подтверждения (уже с токеном).

        Returns:
            provider_message_id или None.
        """
        subject, body = render_verify_email(verify_link)
        return await self._sender.send_email(to=to_email, subject=subject, text=body)
