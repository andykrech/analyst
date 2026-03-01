"""
Тест реального вызова OpenAI Embeddings API через EmbeddingService.
Пропускается, если OPENAI_API_KEY не задан в .env.
При использовании SOCKS-прокси (TUNNEL_PROXY_URL) нужен httpx[socks] (см. requirements.txt).
Запуск из backend/: pytest tests/test_embedding_openai.py -v
"""
import pytest
import httpx

from app.core.config import get_settings
from app.integrations.embedding import EmbeddingService


@pytest.mark.asyncio
async def test_embedding_openai_real_request() -> None:
    """
    Реальный запрос к OpenAI Embeddings: тестовая строка, проверка структуры ответа и вектора.
    При ошибке API выводится статус и тело ответа.
    """
    settings = get_settings()
    api_key = (settings.OPENAI_API_KEY.get_secret_value() or "").strip()
    if not api_key:
        pytest.skip("OPENAI_API_KEY не задан в .env")

    svc = EmbeddingService(settings)
    test_text = "Тестовая строка для эмбеддинга."

    try:
        result = await svc.embed(test_text)
    except httpx.HTTPStatusError as e:
        pytest.fail(
            f"OpenAI API ошибка: {e.response.status_code} — {e.response.text}"
        )
    except httpx.RequestError as e:
        pytest.fail(f"OpenAI API ошибка запроса: {e!r}")
    except Exception as e:
        pytest.fail(f"Ошибка вызова эмбеддинга: {e!r}")

    assert isinstance(result, dict), "Ответ должен быть dict (JSONB)"
    assert "vector" in result, "В ответе должен быть vector"
    assert "cost" in result, "В ответе должен быть cost"

    vector = result["vector"]
    assert isinstance(vector, list), "vector должен быть списком"
    assert len(vector) > 0, "Вектор не должен быть пустым"
    assert all(isinstance(x, (int, float)) for x in vector), "Все элементы вектора — числа"

    expected_dims = settings.EMBEDDING_DIMENSIONS or 1536
    assert len(vector) == expected_dims, f"Размерность вектора должна быть {expected_dims}"

    cost = result["cost"]
    assert isinstance(cost, dict), "cost должен быть dict"
    assert "total_tokens" in cost, "cost должен содержать total_tokens"
    assert "total_cost" in cost, "cost должен содержать total_cost"
    assert cost["total_tokens"] >= 0, "total_tokens неотрицательный"
    assert isinstance(cost["total_cost"], (int, float)), "total_cost — число"

    assert result.get("provider") == "openai"
    assert result.get("model")
    assert result.get("dimensions") == expected_dims
