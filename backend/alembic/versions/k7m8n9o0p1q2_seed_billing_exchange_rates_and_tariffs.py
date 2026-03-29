"""Начальные курсы валют и тарифы биллинга.

Revision ID: k7m8n9o0p1q2
Revises: z9y8x7w6v5u4
Create Date: 2026-03-22

USD/EUR → RUB на 2026-01-01; тарифы с valid_from 2026-01-01 (UTC).
Для embedding в исходном списке не было unit_code — задано total_tokens.
"""

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "k7m8n9o0p1q2"
down_revision: Union[str, Sequence[str], None] = "z9y8x7w6v5u4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Фиксированные UUID для предсказуемого отката.
_EX_USD_RUB = "b1111111-1111-4111-8111-111111111101"
_EX_EUR_RUB = "b1111111-1111-4111-8111-111111111102"

_TARIFF_IDS = (
    "b2222222-2222-4222-8222-222222222201",  # llm deepseek_deepseek_chat_in
    "b2222222-2222-4222-8222-222222222202",  # llm deepseek_deepseek_chat_out
    "b2222222-2222-4222-8222-222222222203",  # embedding openai small
    "b2222222-2222-4222-8222-222222222204",  # translation yandex
    "b2222222-2222-4222-8222-222222222205",  # search openalex
)

# asyncpg не принимает строку для timestamptz — нужен datetime с tzinfo.
_VALID_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            INSERT INTO billing_exchange_rates (
                id, rate_date, from_currency, to_currency, rate
            )
            SELECT CAST(:id AS uuid), '2026-01-01', 'USD', 'RUB', 95.89
            WHERE NOT EXISTS (
                SELECT 1 FROM billing_exchange_rates WHERE id = CAST(:id AS uuid)
            )
            """
        ),
        {"id": _EX_USD_RUB},
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO billing_exchange_rates (
                id, rate_date, from_currency, to_currency, rate
            )
            SELECT CAST(:id AS uuid), '2026-01-01', 'EUR', 'RUB', 111
            WHERE NOT EXISTS (
                SELECT 1 FROM billing_exchange_rates WHERE id = CAST(:id AS uuid)
            )
            """
        ),
        {"id": _EX_EUR_RUB},
    )

    rows = (
        (
            _TARIFF_IDS[0],
            "llm",
            "deepseek_deepseek_chat_in",
            "input_tokens",
            1_000_000,
            "0.14",
            "USD",
        ),
        (
            _TARIFF_IDS[1],
            "llm",
            "deepseek_deepseek_chat_out",
            "output_tokens",
            1_000_000,
            "0.28",
            "USD",
        ),
        (
            _TARIFF_IDS[2],
            "embedding",
            "openai_text-embedding-3-small",
            "total_tokens",
            1_000_000,
            "0.02",
            "USD",
        ),
        (
            _TARIFF_IDS[3],
            "translation",
            "yandex_translator",
            "chars",
            1_000_000,
            "500",
            "RUB",
        ),
        (
            _TARIFF_IDS[4],
            "search",
            "openalex_fulltext-search",
            "requests",
            1_000,
            "1",
            "USD",
        ),
    )
    for (
        tid,
        service_type,
        service_impl,
        unit_code,
        units_per_price,
        price,
        currency_code,
    ) in rows:
        conn.execute(
            sa.text(
                """
                INSERT INTO billing_tariffs (
                    id, service_type, service_impl, unit_code,
                    units_per_price, price, currency_code, valid_from, valid_until
                )
                SELECT
                    CAST(:id AS uuid),
                    :service_type,
                    :service_impl,
                    :unit_code,
                    :units_per_price,
                    CAST(:price AS numeric),
                    :currency_code,
                    :vf,
                    NULL
                WHERE NOT EXISTS (
                    SELECT 1 FROM billing_tariffs WHERE id = CAST(:id AS uuid)
                )
                """
            ),
            {
                "id": tid,
                "service_type": service_type,
                "service_impl": service_impl,
                "unit_code": unit_code,
                "units_per_price": units_per_price,
                "price": price,
                "currency_code": currency_code,
                "vf": _VALID_FROM,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    for tid in _TARIFF_IDS:
        conn.execute(
            sa.text("DELETE FROM billing_tariffs WHERE id = CAST(:id AS uuid)"),
            {"id": tid},
        )
    for eid in (_EX_USD_RUB, _EX_EUR_RUB):
        conn.execute(
            sa.text("DELETE FROM billing_exchange_rates WHERE id = CAST(:id AS uuid)"),
            {"id": eid},
        )
