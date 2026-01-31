import pytest

from kazo.services.currency_service import (
    InvalidCurrencyError,
    _cache_rate,
    _get_cached_rate,
    get_rate,
    validate_currency,
)


def test_validate_valid():
    assert validate_currency("usd") == "USD"
    assert validate_currency("EUR") == "EUR"


def test_validate_invalid():
    with pytest.raises(InvalidCurrencyError):
        validate_currency("XYZ")


def test_validate_bad_format():
    with pytest.raises(InvalidCurrencyError):
        validate_currency("us")


async def test_eur_identity():
    rate = await get_rate("EUR", "EUR")
    assert rate == 1.0


async def test_cache_roundtrip():
    await _cache_rate("USD", "EUR", 0.92)
    cached = await _get_cached_rate("USD", "EUR")
    assert cached == 0.92


async def test_cache_miss():
    cached = await _get_cached_rate("GBP", "EUR")
    assert cached is None
