from datetime import date
from unittest.mock import AsyncMock, patch

from kazo.handlers.subscriptions import _next_billing_date
from kazo.services.subscription_service import (
    add_subscription,
    get_subscriptions,
    refresh_subscription_rates,
    remove_subscription,
)


async def test_add_and_list():
    sub_id = await add_subscription(
        chat_id=1,
        name="Netflix",
        amount=15.99,
        currency="USD",
        amount_eur=14.71,
        frequency="monthly",
    )
    assert sub_id >= 1

    subs = await get_subscriptions(1)
    assert len(subs) == 1
    assert subs[0]["name"] == "Netflix"


async def test_remove():
    await add_subscription(
        chat_id=1,
        name="Spotify",
        amount=9.99,
        currency="EUR",
        amount_eur=9.99,
    )
    removed = await remove_subscription(1, "spotify")
    assert removed is True

    subs = await get_subscriptions(1)
    assert len(subs) == 0


async def test_remove_nonexistent():
    removed = await remove_subscription(1, "nonexistent")
    assert removed is False


@patch("kazo.services.subscription_service.convert_to_base", new_callable=AsyncMock)
@patch("kazo.services.subscription_service.get_base_currency", new_callable=AsyncMock, return_value="EUR")
async def test_refresh_updates_rate(mock_base, mock_convert):
    mock_convert.return_value = (16.50, 1.03)
    await add_subscription(
        chat_id=1,
        name="Netflix",
        amount=15.99,
        currency="USD",
        amount_eur=14.71,
        frequency="monthly",
    )
    await refresh_subscription_rates(1)
    subs = await get_subscriptions(1)
    assert subs[0]["amount_eur"] == 16.50


@patch("kazo.services.subscription_service.convert_to_base", new_callable=AsyncMock)
@patch("kazo.services.subscription_service.get_base_currency", new_callable=AsyncMock, return_value="EUR")
async def test_refresh_skips_eur(mock_base, mock_convert):
    await add_subscription(
        chat_id=1,
        name="Spotify",
        amount=9.99,
        currency="EUR",
        amount_eur=9.99,
    )
    await refresh_subscription_rates(1)
    mock_convert.assert_not_called()


@patch("kazo.services.subscription_service.convert_to_base", new_callable=AsyncMock)
@patch("kazo.services.subscription_service.get_base_currency", new_callable=AsyncMock, return_value="EUR")
async def test_refresh_handles_api_failure(mock_base, mock_convert):
    mock_convert.side_effect = Exception("API down")
    await add_subscription(
        chat_id=1,
        name="Netflix",
        amount=15.99,
        currency="USD",
        amount_eur=14.71,
        frequency="monthly",
    )
    await refresh_subscription_rates(1)
    subs = await get_subscriptions(1)
    assert subs[0]["amount_eur"] == 14.71


async def test_add_subscription_with_billing_day():
    await add_subscription(
        chat_id=1,
        name="Netflix",
        amount=15.99,
        currency="USD",
        amount_eur=14.71,
        frequency="monthly",
        billing_day=15,
    )
    subs = await get_subscriptions(1)
    assert subs[0]["billing_day"] == 15


async def test_add_subscription_without_billing_day():
    await add_subscription(
        chat_id=1,
        name="Spotify",
        amount=9.99,
        currency="EUR",
        amount_eur=9.99,
        frequency="monthly",
    )
    subs = await get_subscriptions(1)
    assert subs[0]["billing_day"] is None


@patch("kazo.handlers.subscriptions.date")
def test_next_billing_date_future(mock_date):
    mock_date.today.return_value = date(2026, 1, 10)
    mock_date.side_effect = lambda *a, **k: date(*a, **k)
    result = _next_billing_date(15, "monthly")
    assert result == date(2026, 1, 15)


@patch("kazo.handlers.subscriptions.date")
def test_next_billing_date_past_rolls_to_next_month(mock_date):
    mock_date.today.return_value = date(2026, 1, 20)
    mock_date.side_effect = lambda *a, **k: date(*a, **k)
    result = _next_billing_date(15, "monthly")
    assert result == date(2026, 2, 15)


@patch("kazo.handlers.subscriptions.date")
def test_next_billing_date_day31_in_feb(mock_date):
    mock_date.today.return_value = date(2026, 2, 1)
    mock_date.side_effect = lambda *a, **k: date(*a, **k)
    result = _next_billing_date(31, "monthly")
    assert result == date(2026, 2, 28)
