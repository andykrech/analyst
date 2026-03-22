"""Ошибки модуля ландшафта темы."""


class LandscapePromptTooLargeError(Exception):
    """Суммарный текст промпта превышает допустимый лимит."""

    def __init__(self, message: str, *, char_count: int, limit: int) -> None:
        super().__init__(message)
        self.char_count = char_count
        self.limit = limit
