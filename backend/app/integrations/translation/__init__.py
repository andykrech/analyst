"""
Интеграция перевода квантов.
Верхний слой — TranslationService; переводчики в translators/ (deepl, ...).
"""

from app.integrations.translation.ports import TranslationCost, TranslationResult, TranslatorPort
from app.integrations.translation.service import TranslationService

__all__ = [
    "TranslationCost",
    "TranslationResult",
    "TranslationService",
    "TranslatorPort",
]
