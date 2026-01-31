import logging
import re
from datetime import UTC, datetime, timedelta

import httpx

from kazo.config import settings
from kazo.currency import get_base_currency
from kazo.db.database import get_db

logger = logging.getLogger(__name__)

SUPPORTED_CURRENCIES: frozenset[str] = frozenset(
    {
        "AUD",
        "BGN",
        "BRL",
        "CAD",
        "CHF",
        "CNY",
        "CZK",
        "DKK",
        "EUR",
        "GBP",
        "HKD",
        "HUF",
        "IDR",
        "ILS",
        "INR",
        "ISK",
        "JPY",
        "KRW",
        "MXN",
        "MYR",
        "NOK",
        "NZD",
        "PHP",
        "PLN",
        "RON",
        "SEK",
        "SGD",
        "THB",
        "TRY",
        "USD",
        "ZAR",
    }
)

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


class InvalidCurrencyError(ValueError):
    def __init__(self, currency: str) -> None:
        self.currency = currency
        super().__init__(f"Unknown currency '{currency}'. Use /rate to see supported currencies.")


def validate_currency(currency: str) -> str:
    code = currency.upper().strip()
    if not _CURRENCY_RE.match(code):
        raise InvalidCurrencyError(currency)
    if code not in SUPPORTED_CURRENCIES:
        raise InvalidCurrencyError(currency)
    return code


def get_supported_currencies() -> list[str]:
    return sorted(SUPPORTED_CURRENCIES)


async def _get_cached_rate(from_currency: str, to_currency: str, allow_stale: bool = False) -> float | None:
    db = await get_db()
    cache_key = f"{from_currency}:{to_currency}"
    cursor = await db.execute(
        "SELECT rate_to_base, fetched_at FROM exchange_rates WHERE currency = ?",
        (cache_key,),
    )
    row = await cursor.fetchone()
    if not row:
        return None
    fetched_at = datetime.fromisoformat(row["fetched_at"])
    age = datetime.now(UTC) - fetched_at.replace(tzinfo=UTC)
    if not allow_stale and age > timedelta(hours=settings.exchange_rate_cache_hours):
        return None
    return row["rate_to_base"]


async def _cache_rate(from_currency: str, to_currency: str, rate: float) -> None:
    db = await get_db()
    cache_key = f"{from_currency}:{to_currency}"
    await db.execute(
        "INSERT OR REPLACE INTO exchange_rates (currency, rate_to_base, fetched_at) VALUES (?, ?, ?)",
        (cache_key, rate, datetime.now(UTC).isoformat()),
    )
    await db.commit()


async def _fetch_rate(from_currency: str, to_currency: str) -> float:
    logger.info("Fetching live rate for %s -> %s", from_currency, to_currency)
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            settings.frankfurter_url,
            params={"from": from_currency, "to": to_currency},
        )
        resp.raise_for_status()
        data = resp.json()
        rate = data["rates"][to_currency]
        logger.info("Fetched rate %s -> %s: %s", from_currency, to_currency, rate)
        return rate


async def get_rate(from_currency: str, to_currency: str) -> float:
    from_currency = validate_currency(from_currency)
    to_currency = validate_currency(to_currency)
    if from_currency == to_currency:
        return 1.0

    if cached := await _get_cached_rate(from_currency, to_currency):
        return cached

    try:
        rate = await _fetch_rate(from_currency, to_currency)
        await _cache_rate(from_currency, to_currency, rate)
        return rate
    except httpx.HTTPError:
        logger.warning("API request failed for %s->%s, checking stale cache", from_currency, to_currency)
        if stale := await _get_cached_rate(from_currency, to_currency, allow_stale=True):
            return stale
        raise


async def convert_to_base(amount: float, currency: str, chat_id: int) -> tuple[float, float]:
    base = await get_base_currency(chat_id)
    rate = await get_rate(currency, base)
    return round(amount * rate, 2), rate


async def get_recently_used_currencies(chat_id: int, limit: int = 5) -> list[str]:
    db = await get_db()
    base = await get_base_currency(chat_id)
    cursor = await db.execute(
        "SELECT DISTINCT original_currency FROM expenses "
        "WHERE chat_id = ? AND original_currency != ? "
        "ORDER BY created_at DESC LIMIT ?",
        (chat_id, base, limit),
    )
    rows = await cursor.fetchall()
    return [row["original_currency"] for row in rows]
