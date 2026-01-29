"""
Интеграция отправки email: абстракция EmailSender + фабрика по EMAIL_PROVIDER.
"""
from app.integrations.email.ports import EmailSender
from app.integrations.email.factory import get_email_sender
from app.integrations.email.service import AuthEmailService

__all__ = [
    "EmailSender",
    "get_email_sender",
    "AuthEmailService",
]
