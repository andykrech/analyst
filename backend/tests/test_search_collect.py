"""
Тест POST /api/v1/search/collect: структура ответа, нормализация URL, дедупликация.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.integrations.search.router import get_search_service
from app.integrations.search.service import SearchService
from app.main import app


@pytest.fixture
def app_with_search():
    """App с SearchService (lifespan не вызывается при ASGITransport)."""
    settings = get_settings()
    app.dependency_overrides[get_search_service] = lambda: SearchService(settings)
    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_collect_structure_and_normalization(app_with_search):
    """Проверка структуры ответа, normalized_url, url_hash, отсутствие дублей."""
    transport = ASGITransport(app=app_with_search)
    payload = {
        "keywords": ["fastapi", "postgres"],
        "must_have": ["fastapi"],
        "exclude": ["casino"],
        "target_links": 20,
    }
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/search/collect", json=payload)

    assert response.status_code == 200, response.text
    data = response.json()

    assert "items" in data
    items = data["items"]
    assert len(items) > 0

    assert "plan" in data
    plan = data["plan"]
    assert "steps" in plan
    assert len(plan["steps"]) > 0

    assert "step_results" in data
    step_results = data["step_results"]
    assert len(step_results) > 0

    assert data["total_returned"] <= 20

    # У каждого item заполнены normalized_url и url_hash
    seen_hashes: set[str] = set()
    for item in items:
        assert "normalized_url" in item
        assert item["normalized_url"] is not None
        assert item["normalized_url"] != ""

        assert "url_hash" in item
        assert item["url_hash"] is not None
        assert item["url_hash"] != ""

        # Нет дублей по url_hash
        h = item["url_hash"]
        assert h not in seen_hashes
        seen_hashes.add(h)
