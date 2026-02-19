"""
Тест POST /api/v1/search/collect: структура ответа (кванты), дедупликация.
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
async def test_search_collect_structure_and_dedup(app_with_search):
    """Проверка структуры ответа (кванты), обязательные поля, отсутствие дублей по dedup_key."""
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

    # Каждый item — квант: theme_id, entity_kind, title, summary_text, verification_url, source_system
    seen_urls: set[str] = set()
    for item in items:
        assert "theme_id" in item
        assert "entity_kind" in item
        assert item["entity_kind"] == "webpage"
        assert "title" in item
        assert item["title"]
        assert "summary_text" in item
        assert item["summary_text"]
        assert "verification_url" in item
        url = item["verification_url"]
        assert url
        assert "source_system" in item
        assert item["source_system"] == "yandex"
        # Нет дублей по verification_url (дедуп в executor по dedup_key/canonical_url)
        assert url not in seen_urls
        seen_urls.add(url)
