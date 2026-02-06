"""
Smoke-проверка промптов: загрузка, уникальность name/alias, рендер theme.init.
Без внешних HTTP-вызовов. Запуск: python -m app.integrations.prompts.smoke
"""
import asyncio
import sys


async def check_prompts_smoke() -> None:
    """
    Загружает промпты, проверяет уникальность name и alias,
    выполняет render("theme.init", {"user_input": "..."}) и проверяет подстановку.
    """
    from app.core.config import get_settings
    from app.integrations.prompts import PromptService, get_prompt_provider

    settings = get_settings()
    provider = get_prompt_provider(settings)
    service = PromptService(provider)

    # Загрузка и список
    meta_list = await service.list_templates()
    names = [m.name for m in meta_list]
    if not names:
        print("FAIL: no prompts loaded")
        sys.exit(1)
    if len(names) != len(set(names)):
        print("FAIL: duplicate prompt names")
        sys.exit(1)

    # Алиасы: у FilePromptProvider есть _alias_to_name (проверка после list — кеш загружен)
    if hasattr(provider, "_alias_to_name"):
        alias_to_name = getattr(provider, "_alias_to_name", {})
        for alias, canonical in alias_to_name.items():
            if canonical not in names:
                print(f"FAIL: alias {alias!r} points to unknown name {canonical!r}")
                sys.exit(1)

    # Рендер theme.init (или theme.init.v1)
    test_vars = {"user_input": "Разработка мобильных приложений на Flutter"}
    try:
        rendered = await service.render("theme.init", test_vars)
    except KeyError:
        rendered = await service.render("theme.init.v1", test_vars)
    if "Разработка мобильных приложений на Flutter" not in rendered.text:
        print("FAIL: placeholder {{user_input}} was not replaced")
        sys.exit(1)
    print("OK: prompts loaded, names/aliases unique, theme.init render ok")


if __name__ == "__main__":
    asyncio.run(check_prompts_smoke())
