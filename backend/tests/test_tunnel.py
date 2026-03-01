"""
Тесты туннеля (прокси): get_httpx_proxy.
"""
import re
from types import SimpleNamespace

import httpx
import pytest

from app.core.config import get_settings
from app.integrations.tunnel import get_httpx_proxy


def test_get_httpx_proxy_returns_none_when_url_empty() -> None:
    """Пустой или отсутствующий TUNNEL_PROXY_URL — возвращается None."""
    settings = SimpleNamespace(TUNNEL_PROXY_URL="")
    assert get_httpx_proxy(settings) is None

    settings = SimpleNamespace(TUNNEL_PROXY_URL="   ")
    assert get_httpx_proxy(settings) is None


def test_get_httpx_proxy_returns_url_when_set() -> None:
    """Заданный URL возвращается без изменений (после strip)."""
    settings = SimpleNamespace(TUNNEL_PROXY_URL="socks5://host:1080")
    assert get_httpx_proxy(settings) == "socks5://host:1080"

    settings = SimpleNamespace(TUNNEL_PROXY_URL="  socks5://user:pass@host:1080  ")
    assert get_httpx_proxy(settings) == "socks5://user:pass@host:1080"

    settings = SimpleNamespace(TUNNEL_PROXY_URL="http://proxy.example.com:3128")
    assert get_httpx_proxy(settings) == "http://proxy.example.com:3128"


@pytest.mark.asyncio
async def test_tunnel_real_request_via_proxy() -> None:
    """
    Реальный запрос к api.ipify.org через прокси из TUNNEL_PROXY_URL (.env).
    Пропускается, если TUNNEL_PROXY_URL не задан. Запуск: pytest из backend/.
    """
    settings = get_settings()
    proxy = get_httpx_proxy(settings)
    if not proxy:
        pytest.skip("TUNNEL_PROXY_URL не задан в .env")

    async with httpx.AsyncClient(proxy=proxy, timeout=15.0) as client:
        response = await client.get("https://api.ipify.org")

    assert response.status_code == 200, response.text
    body = response.text.strip()
    assert re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", body), (
        f"Ожидается IP в теле ответа, получено: {body!r}"
    )
