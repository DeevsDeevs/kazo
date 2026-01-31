import json
from datetime import date

from kazo.db.models import Expense
from kazo.services.expense_service import (
    get_expense_items,
    save_expense,
    save_expense_items,
    search_items_by_name,
)


def _make_expense(**overrides) -> Expense:
    defaults = dict(
        id=None,
        chat_id=1,
        user_id=100,
        store="Lidl",
        amount=25.0,
        original_currency="EUR",
        amount_base=25.0,
        exchange_rate=1.0,
        category="groceries",
        items_json=None,
        source="receipt",
        expense_date=date(2025, 3, 15),
    )
    defaults.update(overrides)
    return Expense(**defaults)


async def test_save_expense_with_items_creates_expense_items():
    items = [{"name": "Tomatoes", "price": 3.50}, {"name": "Bread", "price": 2.20}]
    exp = _make_expense(items_json=json.dumps(items))
    expense_id = await save_expense(exp)

    rows = await get_expense_items(expense_id)
    assert len(rows) == 2
    assert rows[0]["name"] == "Tomatoes"
    assert rows[0]["price"] == 3.50
    assert rows[1]["name"] == "Bread"


async def test_save_expense_without_items_no_expense_items():
    expense_id = await save_expense(_make_expense())
    rows = await get_expense_items(expense_id)
    assert rows == []


async def test_items_with_quantity():
    items = [{"name": "Apples", "price": 1.50, "quantity": 3}]
    exp = _make_expense(items_json=json.dumps(items))
    expense_id = await save_expense(exp)

    rows = await get_expense_items(expense_id)
    assert rows[0]["quantity"] == 3.0


async def test_items_with_item_key():
    items = [{"item": "Milk", "price": 1.20}]
    exp = _make_expense(items_json=json.dumps(items))
    expense_id = await save_expense(exp)

    rows = await get_expense_items(expense_id)
    assert len(rows) == 1
    assert rows[0]["name"] == "Milk"


async def test_invalid_items_json_ignored():
    exp = _make_expense(items_json="not json")
    expense_id = await save_expense(exp)
    rows = await get_expense_items(expense_id)
    assert rows == []


async def test_save_expense_items_replaces():
    expense_id = await save_expense(_make_expense())
    await save_expense_items(expense_id, [{"name": "A", "price": 1.0}], "EUR")
    await save_expense_items(expense_id, [{"name": "B", "price": 2.0}], "EUR")

    rows = await get_expense_items(expense_id)
    assert len(rows) == 1
    assert rows[0]["name"] == "B"


async def test_search_items_by_name():
    items = [{"name": "Cherry Tomatoes", "price": 4.0}]
    exp = _make_expense(items_json=json.dumps(items))
    await save_expense(exp)

    results = await search_items_by_name("tomato", chat_id=1)
    assert len(results) == 1
    assert results[0]["name"] == "Cherry Tomatoes"
    assert results[0]["store"] == "Lidl"


async def test_search_items_wrong_chat():
    items = [{"name": "Cheese", "price": 5.0}]
    await save_expense(_make_expense(items_json=json.dumps(items)))

    results = await search_items_by_name("Cheese", chat_id=999)
    assert results == []


async def test_cascade_delete_items(test_db):
    items = [{"name": "Water", "price": 1.0}]
    exp = _make_expense(items_json=json.dumps(items))
    expense_id = await save_expense(exp)

    await test_db.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    await test_db.commit()

    rows = await get_expense_items(expense_id)
    assert rows == []
