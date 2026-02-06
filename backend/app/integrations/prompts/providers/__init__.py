"""
Провайдеры промптов: file, db (позже).
"""
from app.integrations.prompts.providers.file_provider import FilePromptProvider

__all__ = ["FilePromptProvider"]
