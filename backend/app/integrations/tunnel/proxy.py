"""
Обёртки для работы с прокси (туннель): значение для httpx.AsyncClient(proxy=...).
"""
from app.core.config import Settings


def get_httpx_proxy(settings: Settings) -> str | None:
    """
    Вернуть URL прокси для httpx или None, если туннель не настроен.

    Использование:
        proxy = get_httpx_proxy(get_settings())
        async with httpx.AsyncClient(proxy=proxy) as client:
            ...

    Поддерживаются схемы: socks5://, socks4://, http://.
    Для SOCKS5 нужна зависимость: httpx[socks].
    """
    url = (settings.TUNNEL_PROXY_URL or "").strip()
    return url if url else None
