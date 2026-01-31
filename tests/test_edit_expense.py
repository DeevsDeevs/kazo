from datetime import date

from kazo.db.models import Expense
from kazo.services.expense_service import (
    get_expense_by_bot_message,
    get_expense_by_id,
    get_last_expense,
    link_bot_message,
    save_expense,
    update_expense,
)


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


async def test_get_expense_by_id():
    exp_id = await save_expense(_make_expense())
    result = await get_expense_by_id(exp_id)
    assert result is not None
    assert result["amount"] == 25.0


async def test_get_expense_by_id_not_found():
    result = await get_expense_by_id(9999)
    assert result is None


async def test_update_expense_category():
    exp_id = await save_expense(_make_expense())
    updated = await update_expense(exp_id, category="dining")
    assert updated is True
    result = await get_expense_by_id(exp_id)
    assert result["category"] == "dining"


async def test_update_expense_amount():
    exp_id = await save_expense(_make_expense())
    updated = await update_expense(exp_id, amount=50.0, amount_eur=50.0)
    assert updated is True
    result = await get_expense_by_id(exp_id)
    assert result["amount"] == 50.0
    assert result["amount_eur"] == 50.0


async def test_update_expense_no_fields():
    exp_id = await save_expense(_make_expense())
    updated = await update_expense(exp_id)
    assert updated is False


async def test_update_expense_disallowed_field():
    exp_id = await save_expense(_make_expense())
    updated = await update_expense(exp_id, id=999, chat_id=999)
    assert updated is False


async def test_link_and_get_bot_message():
    exp_id = await save_expense(_make_expense())
    await link_bot_message(chat_id=1, bot_message_id=500, expense_id=exp_id)

    result = await get_expense_by_bot_message(chat_id=1, bot_message_id=500)
    assert result is not None
    assert result["id"] == exp_id


async def test_get_bot_message_not_found():
    result = await get_expense_by_bot_message(chat_id=1, bot_message_id=9999)
    assert result is None


async def test_get_last_expense():
    await save_expense(_make_expense(amount=10.0, amount_eur=10.0))
    await save_expense(_make_expense(amount=20.0, amount_eur=20.0))
    result = await get_last_expense(chat_id=1)
    assert result is not None
    assert result["amount"] == 20.0


async def test_get_last_expense_empty():
    result = await get_last_expense(chat_id=9999)
    assert result is None
