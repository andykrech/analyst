"""
Туннель (прокси): настройки для HTTP-клиентов интеграций, которые идут через прокси.
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.config import Settings

from app.integrations.tunnel.proxy import get_httpx_proxy

__all__ = ["get_httpx_proxy"]
