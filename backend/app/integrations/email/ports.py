"""
Интерфейс отправки email (port).
"""
from abc import ABC, abstractmethod


class EmailSender(ABC):
    """Абстракция для отправки транзакционных писем."""

    @abstractmethod
    async def send_email(self, to: str, subject: str, text: str) -> str | None:
        """
        Отправить письмо.

        Args:
            to: Email получателя.
            subject: Тема письма.
            text: Текст письма (plain text).

        Returns:
            provider_message_id — идентификатор сообщения у провайдера, если есть; иначе None.
        """
        ...
