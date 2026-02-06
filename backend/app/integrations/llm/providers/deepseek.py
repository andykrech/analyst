"""
Провайдер DeepSeek: вызов API chat/completions.
Не считает стоимость и токены — это делает LLMService.
"""
import logging
from typing import Any

import httpx

from app.core.config import ProviderConfig
from app.integrations.llm.types import LLMRequest

logger = logging.getLogger(__name__)

RAW_MAX_LEN = 5000


class DeepSeekProvider:
    """Вызов DeepSeek API (OpenAI-совместимый chat/completions)."""

    def __init__(self, config: ProviderConfig, http_client: httpx.AsyncClient) -> None:
        self._config = config
        self._client = http_client

    async def generate(self, request: LLMRequest) -> dict:
        """
        POST {base_url}/chat/completions.
        Возвращает dict: text, raw (до RAW_MAX_LEN), model, usage (если есть), finish_reason.
        """
        body: dict[str, Any] = {
            "model": self._config.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }
        if request.generation:
            if request.generation.temperature is not None:
                body["temperature"] = request.generation.temperature
            if request.generation.max_tokens is not None:
                body["max_tokens"] = request.generation.max_tokens
            if request.generation.top_p is not None:
                body["top_p"] = request.generation.top_p

        url = f"{self._config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._config.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

        response = await self._client.post(
            url,
            json=body,
            headers=headers,
            timeout=float(self._config.timeout_s),
        )
        response.raise_for_status()
        data = response.json()

        choices = data.get("choices") or []
        text = ""
        finish_reason: str | None = None
        if choices:
            choice = choices[0]
            text = (choice.get("message") or {}).get("content") or ""
            finish_reason = choice.get("finish_reason")

        usage_raw = data.get("usage")
        usage: dict | None = None
        if usage_raw and isinstance(usage_raw, dict):
            pt = usage_raw.get("prompt_tokens")
            ct = usage_raw.get("completion_tokens")
            tt = usage_raw.get("total_tokens")
            if pt is not None and ct is not None:
                usage = {
                    "prompt_tokens": int(pt),
                    "completion_tokens": int(ct),
                    "total_tokens": int(tt) if tt is not None else int(pt) + int(ct),
                }

        raw_str = str(data)
        if len(raw_str) > RAW_MAX_LEN:
            raw_str = raw_str[:RAW_MAX_LEN] + "..."

        return {
            "text": text,
            "raw": raw_str,
            "model": data.get("model") or self._config.model,
            "usage": usage,
            "finish_reason": finish_reason,
        }
