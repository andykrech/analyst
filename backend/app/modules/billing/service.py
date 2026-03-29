"""Запись событий биллинга: тариф из БД, курс, валюта отображения темы."""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.exceptions import BillingConfigError
from app.modules.billing.model import (
    BillingDailyServicesTasks,
    BillingExchangeRate,
    BillingTariff,
    BillingUsageEvent,
)
from app.modules.entity.model import ThemeStats

logger = logging.getLogger(__name__)

# Сколько полных локальных календарных дней «буфера» оставляем до свёртки (сегодня − N).
_BILLING_ROLLUP_LAG_DAYS = 2

# Минимум 6 знаков после запятой для денежных полей в событии
_MONEY_QUANT = Decimal("1.000000")

# UPSERT по уникальному выраженному индексу (COALESCE(service_impl, '')); constraint name не подходит.
_DAILY_SUMMARY_UPSERT = text(
    """
    INSERT INTO billing_daily_summaries (
        theme_id, summary_local_date, service_type, task_type,
        quantity_unit_code, tariff_currency_code, service_impl,
        sum_quantity, sum_cost_tariff_currency, sum_cost_display_currency,
        display_currency_code
    ) VALUES (
        :theme_id, :summary_local_date, :service_type, :task_type,
        :quantity_unit_code, :tariff_currency_code, :service_impl,
        :sum_quantity, :sum_cost_tariff_currency, :sum_cost_display_currency,
        :display_currency_code
    )
    ON CONFLICT (
        theme_id,
        summary_local_date,
        service_type,
        task_type,
        quantity_unit_code,
        tariff_currency_code,
        (COALESCE(service_impl, ''))
    ) DO UPDATE SET
        sum_quantity = billing_daily_summaries.sum_quantity + EXCLUDED.sum_quantity,
        sum_cost_tariff_currency = billing_daily_summaries.sum_cost_tariff_currency
            + EXCLUDED.sum_cost_tariff_currency,
        sum_cost_display_currency = billing_daily_summaries.sum_cost_display_currency
            + EXCLUDED.sum_cost_display_currency,
        display_currency_code = EXCLUDED.display_currency_code,
        updated_at = now()
    """
)


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)


class BillingService:
    """Расчёт стоимости по тарифам/курсам и вставка строки в billing_usage_events."""

    async def record_usage(
        self,
        session: AsyncSession,
        *,
        theme_id: uuid.UUID,
        task_type: str,
        service_type: str,
        service_impl: str,
        quantity: Decimal,
        quantity_unit_code: str,
        occurred_at: datetime | None = None,
        extra: dict[str, Any] | None = None,
    ) -> BillingUsageEvent:
        """
        Найти тариф и курс, посчитать суммы (≥ 6 знаков после запятой), вставить событие.

        При отсутствии тарифа или курса — BillingConfigError.
        """
        if quantity <= 0:
            raise ValueError("quantity must be positive for billing record")
        at = occurred_at if occurred_at is not None else datetime.now(timezone.utc)
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)

        stats = await self._get_theme_billing_settings(session, theme_id)
        display_ccy = stats["display_currency"]
        tz_name = stats["timezone"]

        tariff = await self._resolve_tariff(
            session,
            service_type=service_type,
            service_impl=service_impl,
            unit_code=quantity_unit_code,
            at=at,
        )
        if tariff is None:
            raise BillingConfigError(
                f"No billing tariff for service_type={service_type!r} "
                f"service_impl={service_impl!r} unit_code={quantity_unit_code!r} at {at!r}",
            )

        units_per = Decimal(str(tariff.units_per_price))
        if units_per <= 0:
            raise BillingConfigError("Invalid tariff: units_per_price must be positive")

        price = Decimal(str(tariff.price))
        tariff_ccy = tariff.currency_code.upper()
        cost_tariff = _money((quantity / units_per) * price)

        rate_row: BillingExchangeRate | None = None
        if tariff_ccy == display_ccy.upper():
            cost_display = cost_tariff
        else:
            rate_date = self._local_date_for_theme(at, tz_name)
            rate_row = await self._resolve_exchange_rate(
                session,
                rate_date=rate_date,
                from_currency=tariff_ccy,
                to_currency=display_ccy.upper(),
            )
            if rate_row is None:
                raise BillingConfigError(
                    f"No exchange rate {tariff_ccy!r} -> {display_ccy.upper()!r} on date {rate_date}",
                )
            rate = Decimal(str(rate_row.rate))
            cost_display = _money(cost_tariff * rate)

        impl = (service_impl or "").strip() or None

        row = BillingUsageEvent(
            theme_id=theme_id,
            occurred_at=at,
            service_type=service_type,
            task_type=task_type,
            service_impl=impl,
            quantity=quantity,
            quantity_unit_code=quantity_unit_code,
            extra=extra,
            cost_tariff_currency=cost_tariff,
            tariff_currency_code=tariff_ccy,
            cost_display_currency=cost_display,
            display_currency_code=display_ccy.upper(),
            tariff_id=tariff.id,
            exchange_rate_id=rate_row.id if rate_row else None,
            deleted=False,
        )
        session.add(row)
        await session.flush()
        return row

    async def _get_theme_billing_settings(
        self,
        session: AsyncSession,
        theme_id: uuid.UUID,
    ) -> dict[str, str]:
        q = await session.execute(
            select(ThemeStats.billing_display_currency, ThemeStats.billing_timezone)
            .where(ThemeStats.theme_id == theme_id)
            .order_by(ThemeStats.id)
            .limit(1),
        )
        row = q.first()
        if row is None:
            return {
                "display_currency": "RUB",
                "timezone": "Asia/Krasnoyarsk",
            }
        ccy, tz = row[0], row[1]
        return {
            "display_currency": (ccy or "RUB").strip().upper()[:3],
            "timezone": (tz or "Asia/Krasnoyarsk").strip(),
        }

    async def _resolve_tariff(
        self,
        session: AsyncSession,
        *,
        service_type: str,
        service_impl: str,
        unit_code: str,
        at: datetime,
    ) -> BillingTariff | None:
        stmt = (
            select(BillingTariff)
            .where(
                BillingTariff.service_type == service_type,
                BillingTariff.service_impl == service_impl,
                BillingTariff.unit_code == unit_code,
                BillingTariff.valid_from <= at,
                or_(BillingTariff.valid_until.is_(None), BillingTariff.valid_until > at),
            )
            .order_by(BillingTariff.valid_from.desc())
            .limit(1)
        )
        res = await session.execute(stmt)
        return res.scalars().first()

    def _local_date_for_theme(self, at_utc: datetime, tz_name: str) -> date:
        try:
            from zoneinfo import ZoneInfo

            zi = ZoneInfo(tz_name)
        except Exception:
            from zoneinfo import ZoneInfo

            zi = ZoneInfo("UTC")
        return at_utc.astimezone(zi).date()

    async def _resolve_exchange_rate(
        self,
        session: AsyncSession,
        *,
        rate_date: date,
        from_currency: str,
        to_currency: str,
    ) -> BillingExchangeRate | None:
        # Берём ближайший курс на дату или раньше:
        # сиды могут содержать не ежедневные значения.
        stmt = (
            select(BillingExchangeRate)
            .where(
                and_(
                    BillingExchangeRate.rate_date <= rate_date,
                    BillingExchangeRate.from_currency == from_currency,
                    BillingExchangeRate.to_currency == to_currency,
                ),
            )
            .order_by(BillingExchangeRate.rate_date.desc())
            .limit(1)
        )
        res = await session.execute(stmt)
        return res.scalars().first()

    async def rollup_usage_events_to_daily(self, session: AsyncSession) -> int:
        """
        Свернуть детальные billing_usage_events в billing_daily_summaries.

        Условие: локальная дата события (timezone из theme_stats для темы, иначе как в
        record_usage) <= «сегодня» в том же timezone − _BILLING_ROLLUP_LAG_DAYS
        календарных дней (не 48 часов).

        Группировка: theme_id, summary_local_date, service_type, task_type,
        quantity_unit_code, tariff_currency_code, service_impl (пустое → как COALESCE в индексе).

        При конфликте по ключу — суммы прибавляются (UPSERT). Обработанным строкам
        выставляется deleted=True.

        Returns:
            Число помеченных детальных событий.
        """
        stats_rows = (
            await session.execute(
                select(ThemeStats.theme_id, ThemeStats.billing_timezone, ThemeStats.billing_display_currency)
                .order_by(ThemeStats.theme_id, ThemeStats.id),
            )
        ).all()
        theme_settings: dict[uuid.UUID, tuple[str, str]] = {}
        for tid, tz_raw, ccy_raw in stats_rows:
            if tid not in theme_settings:
                tz_name = (tz_raw or "").strip() or "Asia/Krasnoyarsk"
                ccy = (ccy_raw or "RUB").strip().upper()[:3] or "RUB"
                theme_settings[tid] = (tz_name, ccy)

        ev_res = await session.execute(
            select(BillingUsageEvent).where(BillingUsageEvent.deleted.is_(False)),
        )
        events = list(ev_res.scalars().all())
        if not events:
            return 0

        from zoneinfo import ZoneInfo

        def _zone(tz_name: str):
            try:
                return ZoneInfo(tz_name.strip())
            except Exception:
                return ZoneInfo("UTC")

        # key -> {sums + display_ccy}; service_impl в ключе — нормализованная строка (пустая = один слот)
        buckets: dict[
            tuple[uuid.UUID, date, str, str, str, str, str],
            dict[str, Any],
        ] = defaultdict(
            lambda: {
                "sum_quantity": Decimal(0),
                "sum_cost_tariff_currency": Decimal(0),
                "sum_cost_display_currency": Decimal(0),
                "display_currency_code": "",
                "ids": [],
            },
        )

        for e in events:
            tid = e.theme_id
            tz_name, _ = theme_settings.get(tid, ("Asia/Krasnoyarsk", "RUB"))
            zi = _zone(tz_name)
            local_d = e.occurred_at.astimezone(zi).date()
            today_local = datetime.now(zi).date()
            last_foldable = today_local - timedelta(days=_BILLING_ROLLUP_LAG_DAYS)
            if local_d > last_foldable:
                continue

            impl_key = (e.service_impl or "").strip()
            key = (
                tid,
                local_d,
                e.service_type,
                e.task_type,
                e.quantity_unit_code,
                e.tariff_currency_code.upper(),
                impl_key,
            )
            b = buckets[key]
            b["sum_quantity"] += Decimal(str(e.quantity))
            b["sum_cost_tariff_currency"] += Decimal(str(e.cost_tariff_currency))
            b["sum_cost_display_currency"] += Decimal(str(e.cost_display_currency))
            if not b["display_currency_code"]:
                b["display_currency_code"] = (e.display_currency_code or "").strip().upper()[:3] or "RUB"
            b["ids"].append(e.id)

        if not buckets:
            return 0

        task_deltas: dict[tuple[uuid.UUID, date, str, str, str], Decimal] = defaultdict(
            lambda: Decimal(0),
        )

        for key, b in buckets.items():
            (
                theme_id,
                summary_local_date,
                service_type,
                task_type,
                quantity_unit_code,
                tariff_currency_code,
                impl_key,
            ) = key
            sq = _money(b["sum_quantity"])
            sct = _money(b["sum_cost_tariff_currency"])
            scd = _money(b["sum_cost_display_currency"])
            dcc = b["display_currency_code"] or "RUB"
            impl_db = impl_key if impl_key else None

            await session.execute(
                _DAILY_SUMMARY_UPSERT,
                {
                    "theme_id": theme_id,
                    "summary_local_date": summary_local_date,
                    "service_type": service_type,
                    "task_type": task_type,
                    "quantity_unit_code": quantity_unit_code,
                    "tariff_currency_code": tariff_currency_code,
                    "service_impl": impl_db,
                    "sum_quantity": sq,
                    "sum_cost_tariff_currency": sct,
                    "sum_cost_display_currency": scd,
                    "display_currency_code": dcc,
                },
            )

            tk = (theme_id, summary_local_date, service_type, task_type, dcc)
            task_deltas[tk] += scd

        for (theme_id, summary_local_date, service_type, task_type, dcc), add_amt in task_deltas.items():
            amt = _money(add_amt)
            insert_stmt = pg_insert(BillingDailyServicesTasks).values(
                theme_id=theme_id,
                summary_local_date=summary_local_date,
                service_type=service_type,
                task_type=task_type,
                sum_cost_display_currency=amt,
                display_currency_code=dcc,
            )
            upsert_tasks = insert_stmt.on_conflict_do_update(
                constraint="uq_billing_daily_services_tasks_slice",
                set_={
                    "sum_cost_display_currency": BillingDailyServicesTasks.sum_cost_display_currency
                    + insert_stmt.excluded.sum_cost_display_currency,
                    "updated_at": func.now(),
                },
            )
            await session.execute(upsert_tasks)

        all_ids: list[uuid.UUID] = []
        for b in buckets.values():
            all_ids.extend(b["ids"])

        await session.execute(
            update(BillingUsageEvent)
            .where(BillingUsageEvent.id.in_(all_ids))
            .values(deleted=True),
        )

        logger.info(
            "billing rollup: свернуто детальных событий=%s, уникальных срезов сводки=%s",
            len(all_ids),
            len(buckets),
        )
        return len(all_ids)


if TYPE_CHECKING:
    from fastapi import Request


def get_billing_service(request: "Request") -> BillingService:
    """FastAPI Depends: BillingService из app.state."""
    return request.app.state.billing_service
