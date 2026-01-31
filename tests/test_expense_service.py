from datetime import date

from kazo.db.models import Expense
from kazo.services.expense_service import delete_last_expense, detect_recurring, get_expenses, save_expense


def _make_expense(**overrides) -> Expense:
    defaults = dict(
        id=None,
        chat_id=1,
        user_id=100,
        store="TestStore",
        amount=25.0,
        original_currency="EUR",
        amount_eur=25.0,
        exchange_rate=1.0,
        category="groceries",
        items_json=None,
        source="text",
        expense_date=date(2025, 3, 15),
    )
    defaults.update(overrides)
    return Expense(**defaults)


async def test_save_and_retrieve():
    exp = _make_expense()
    row_id = await save_expense(exp)
    assert row_id >= 1

    rows = await get_expenses(chat_id=1)
    assert len(rows) == 1
    assert rows[0]["amount"] == 25.0
    assert rows[0]["store"] == "TestStore"


async def test_date_filter():
    await save_expense(_make_expense(expense_date=date(2025, 1, 10)))
    await save_expense(_make_expense(expense_date=date(2025, 2, 15)))
    await save_expense(_make_expense(expense_date=date(2025, 3, 20)))

    rows = await get_expenses(1, start_date=date(2025, 2, 1), end_date=date(2025, 2, 28))
    assert len(rows) == 1
    assert rows[0]["amount_eur"] == 25.0


async def test_empty_result():
    rows = await get_expenses(chat_id=999)
    assert rows == []


async def test_delete_last_expense():
    await save_expense(_make_expense(amount=10.0, amount_eur=10.0))
    await save_expense(_make_expense(amount=20.0, amount_eur=20.0))

    deleted = await delete_last_expense(chat_id=1)
    assert deleted is not None
    assert deleted["amount_eur"] == 20.0

    rows = await get_expenses(chat_id=1)
    assert len(rows) == 1
    assert rows[0]["amount_eur"] == 10.0


async def test_delete_last_expense_empty():
    result = await delete_last_expense(chat_id=999)
    assert result is None


async def test_detect_recurring_triggers():
    today = date.today()
    for _i in range(2):
        await save_expense(_make_expense(store="Netflix", amount=15.99, amount_eur=15.99, expense_date=today))
    assert await detect_recurring(1, "Netflix", 15.99) is True


async def test_detect_recurring_within_tolerance():
    today = date.today()
    await save_expense(_make_expense(store="Spotify", amount=9.99, amount_eur=9.99, expense_date=today))
    await save_expense(_make_expense(store="Spotify", amount=10.50, amount_eur=10.50, expense_date=today))
    assert await detect_recurring(1, "Spotify", 10.00) is True


async def test_detect_recurring_not_enough():
    today = date.today()
    await save_expense(_make_expense(store="OneTime", amount=50.0, amount_eur=50.0, expense_date=today))
    assert await detect_recurring(1, "OneTime", 50.0) is False


async def test_detect_recurring_no_store():
    assert await detect_recurring(1, "", 10.0) is False
    assert await detect_recurring(1, None, 10.0) is False
