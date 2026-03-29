"""
Биллинг перевода: после translate_quanta_create_items в БД появляется billing_usage_events.

Переводчик подменяется фейком (без DeepL/Yandex API). Нужны применённые миграции и сид
тарифа translation / yandex_translator / chars (k7m8n9o0p1q2).

База в контейнере: имя хоста `db` из docker-compose с хоста не резолвится. Для pytest
с машины разработчика укажите URL на localhost и проброшенный порт, например
`postgresql+asyncpg://...@127.0.0.1:5432/...`, либо переопределите только для тестов:
`TEST_DATABASE_URL=... pytest ...` (если задан — подменяет подключение теста).

Запуск из backend/: pytest tests/test_translation_billing.py -v
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import load_dotenv
from sqlalchemy import select, text

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_test_db_url = (os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
if not _test_db_url:
    pytest.skip(
        "Нет TEST_DATABASE_URL/DATABASE_URL — пропуск интеграционного теста биллинга перевода",
        allow_module_level=True,
    )

# Подмена URL до импорта session (там читается os.environ при загрузке модуля).
os.environ["DATABASE_URL"] = _test_db_url

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.integrations.translation.ports import TranslationCost, TranslationResult
from app.integrations.translation.service import TranslationService
from app.modules.billing.model import BillingUsageEvent
from app.modules.billing.service import BillingService
from app.modules.quanta.schemas import QuantumCreate
import app.modules.site.models  # noqa: F401 — UserSite/ThemeSite для relationship User/Theme
from app.modules.theme.model import Theme
from app.modules.user.model import User


class _FakeYandexTranslator:
    """Имя совпадает с service_impl в сиде тарифа перевода."""

    name = "yandex_translator"

    async def translate(
        self,
        items: list[tuple[int, str, str, list[str]]],
        source_lang: str,
        target_lang: str,
    ) -> TranslationResult:
        n = 0
        translations_by_index: dict[int, dict[str, object]] = {}
        for idx, title, summary, points in items:
            n += len(title) + len(summary) + sum(len(p) for p in points)
            translations_by_index[idx] = {
                "title_translated": f"{title} [t]",
                "summary_text_translated": f"{summary} [t]",
                "key_points_translated": [f"{p} [t]" for p in points],
            }
        return TranslationResult(
            translations_by_index=translations_by_index,
            cost=TranslationCost(input_characters=n),
        )


@pytest.mark.asyncio
async def test_translation_phrase_writes_billing_usage_event() -> None:
    """
    Фраза уходит в (мок) переводчик; в журнал биллинга пишется объём в символах и стоимость в RUB
    по тарифу из БД (тариф в валюте RUB — без курса).
    """
    settings = get_settings()
    billing = BillingService()
    svc = TranslationService(settings, billing_service=billing)
    fake = _FakeYandexTranslator()

    uid = uuid.uuid4()
    tid = uuid.uuid4()
    suffix = uid.hex[:12]
    phrase_title = "Hello"
    phrase_summary = "world"
    expected_chars = len(phrase_title) + len(phrase_summary)
    # Тариф сида: 500 RUB за 1_000_000 символов
    expected_cost_rub = (Decimal(expected_chars) / Decimal(1_000_000)) * Decimal("500")
    expected_cost_rub = expected_cost_rub.quantize(Decimal("1.000000"))

    async with AsyncSessionLocal() as session:
        try:
            session.add(
                User(
                    id=uid,
                    email=f"billing_translation_test_{suffix}@example.invalid",
                )
            )
            session.add(
                Theme(
                    id=tid,
                    user_id=uid,
                    title="billing translation test",
                    description="test",
                )
            )
            await session.commit()

            item = QuantumCreate(
                theme_id=str(tid),
                entity_kind="webpage",
                title=phrase_title,
                summary_text=phrase_summary,
                language="en",
                verification_url="https://example.com/t",
                source_system="test",
                retriever_name="test",
            )

            with patch.object(svc, "_get_translator", return_value=fake):
                await svc.translate_quanta_create_items(
                    [item],
                    target_lang="ru",
                    billing_session=session,
                    billing_theme_id=tid,
                )

            res = await session.execute(
                select(BillingUsageEvent)
                .where(
                    BillingUsageEvent.theme_id == tid,
                    BillingUsageEvent.service_type == "translation",
                    BillingUsageEvent.task_type == "quanta_translation",
                )
                .order_by(BillingUsageEvent.occurred_at.desc())
                .limit(1)
            )
            row = res.scalars().first()
            assert row is not None, "ожидалась строка billing_usage_events"
            assert row.quantity == Decimal(expected_chars)
            assert row.quantity_unit_code == "chars"
            assert row.tariff_currency_code == "RUB"
            assert row.display_currency_code == "RUB"
            assert row.cost_tariff_currency == expected_cost_rub
            assert row.cost_display_currency == expected_cost_rub
            assert row.extra is not None
            assert row.extra.get("translator") == "yandex_translator"
        finally:
            # Сырой SQL: ORM delete() тянет мапперы Theme → ThemeSite без полного импорта моделей.
            await session.execute(
                text("DELETE FROM billing_usage_events WHERE theme_id = CAST(:tid AS uuid)"),
                {"tid": str(tid)},
            )
            await session.execute(
                text("DELETE FROM themes WHERE id = CAST(:tid AS uuid)"),
                {"tid": str(tid)},
            )
            await session.execute(
                text("DELETE FROM users WHERE id = CAST(:uid AS uuid)"),
                {"uid": str(uid)},
            )
            await session.commit()
