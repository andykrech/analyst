"""Ошибки конфигурации и расчёта биллинга."""


class BillingError(Exception):
    """Базовое исключение биллинга."""


class BillingConfigError(BillingError):
    """Нет тарифа, курса или настроек темы, необходимых для расчёта."""
