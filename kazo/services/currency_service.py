import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

from kazo.config import settings
from kazo.db.database import get_db

logger = logging.getLogger(__name__)

SUPPORTED_CURRENCIES: frozenset[str] = frozenset({
    "AUD", "BGN", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR", "GBP",
    "HKD", "HUF", "IDR", "ILS", "INR", "ISK", "JPY", "KRW", "MXN", "MYR",
    "NOK", "NZD", "PHP", "PLN", "RON", "SEK", "SGD", "THB", "TRY", "USD",
    "ZAR",
})

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


class InvalidCurrencyError(ValueError):
    def __init__(self, currency: str) -> None:
        self.currency = currency
        super().__init__(
            f"Unknown currency '{currency}'. "
            f"Use /rate to see supported currencies."
        )


def validate_currency(currency: str) -> str:
    code = currency.upper().strip()
    if not _CURRENCY_RE.match(code):
        raise InvalidCurrencyError(currency)
    if code not in SUPPORTED_CURRENCIES:
        raise InvalidCurrencyError(currency)
    return code


def get_supported_currencies() -> list[str]:
    return sorted(SUPPORTED_CURRENCIES)


async def _get_cached_rate(currency: str, allow_stale: bool = False) -> float | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT rate_to_eur, fetched_at FROM exchange_rates WHERE currency = ?",
        (currency,),
    )
    row = await cursor.fetchone()
    if not row:
        return None
    fetched_at = datetime.fromisoformat(row["fetched_at"])
    age = datetime.now(timezone.utc) - fetched_at.replace(tzinfo=timezone.utc)
    if not allow_stale and age > timedelta(hours=settings.exchange_rate_cache_hours):
        logger.debug("Cache expired for %s (age=%s)", currency, age)
        return None
    logger.debug("Cache hit for %s (age=%s, stale=%s)", currency, age, allow_stale)
    return row["rate_to_eur"]


async def _cache_rate(currency: str, rate: float) -> None:
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO exchange_rates (currency, rate_to_eur, fetched_at) VALUES (?, ?, ?)",
        (currency, rate, datetime.now(timezone.utc).isoformat()),
    )
    await db.commit()
    logger.debug("Cached rate %s -> EUR: %s", currency, rate)


async def _fetch_rate(currency: str) -> float:
    logger.info("Fetching live rate for %s -> EUR", currency)
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            settings.frankfurter_url,
            params={"from": currency, "to": "EUR"},
        )
        resp.raise_for_status()
        data = resp.json()
        rate = data["rates"]["EUR"]
        logger.info("Fetched rate %s -> EUR: %s", currency, rate)
        return rate


async def get_rate_to_eur(currency: str) -> float:
    currency = validate_currency(currency)
    if currency == "EUR":
        return 1.0

    if cached := await _get_cached_rate(currency):
        return cached

    try:
        rate = await _fetch_rate(currency)
        await _cache_rate(currency, rate)
        return rate
    except httpx.HTTPError:
        logger.warning("API request failed for %s, checking stale cache", currency)
        if stale := await _get_cached_rate(currency, allow_stale=True):
            logger.warning("Using stale cached rate for %s: %s", currency, stale)
            return stale
        logger.error("No cached rate available for %s", currency)
        raise


async def convert_to_eur(amount: float, currency: str) -> tuple[float, float]:
    rate = await get_rate_to_eur(currency)
    return round(amount * rate, 2), rate


async def get_recently_used_currencies(chat_id: int, limit: int = 5) -> list[str]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT DISTINCT original_currency FROM expenses "
        "WHERE chat_id = ? AND original_currency != 'EUR' "
        "ORDER BY created_at DESC LIMIT ?",
        (chat_id, limit),
    )
    rows = await cursor.fetchall()
    return [row["original_currency"] for row in rows]
