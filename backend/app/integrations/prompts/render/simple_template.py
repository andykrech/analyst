"""
Простая подстановка переменных {{var}} в шаблоне.
Перед рендером проверяет, что все placeholders присутствуют в vars.
"""
import re
from typing import Any


def render(template: str, vars: dict[str, Any], placeholders: list[str] | None = None) -> str:
    """
    Подставить в template значения из vars для плейсхолдеров {{key}}.

    Если передан placeholders — все перечисленные ключи должны быть в vars,
    иначе ValueError с указанием недостающего ключа.
    Нестроковые значения приводятся к str(value).
    """
    if placeholders:
        for key in placeholders:
            if key not in vars:
                raise ValueError(f"Missing placeholder value: {key!r}")
    # Находим все {{...}} и подставляем
    pattern = re.compile(r"\{\{(\w+)\}\}")

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in vars:
            raise ValueError(f"Missing placeholder value: {key!r}")
        return str(vars[key])

    return pattern.sub(repl, template)
