import pytest

from kazo.services.currency_service import (
    validate_currency, InvalidCurrencyError, convert_to_eur,
    _cache_rate, _get_cached_rate,
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
    amount_eur, rate = await convert_to_eur(100.0, "EUR")
    assert amount_eur == 100.0
    assert rate == 1.0


async def test_cache_roundtrip():
    await _cache_rate("USD", 0.92)
    cached = await _get_cached_rate("USD")
    assert cached == 0.92


async def test_cache_miss():
    cached = await _get_cached_rate("GBP")
    assert cached is None
