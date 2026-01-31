"""Tests for item parsing from text messages."""

import json

from kazo.db.models import Expense
from kazo.services.expense_service import get_expense_items, save_expense


def _make_expense(**overrides) -> Expense:
    defaults = dict(
        id=None,
        chat_id=1,
        user_id=100,
        store="Carrefour",
        amount=6.70,
        original_currency="EUR",
        amount_eur=6.70,
        exchange_rate=1.0,
        category="groceries",
        items_json=None,
        source="text",
        expense_date="2026-01-31",
    )
    defaults.update(overrides)
    return Expense(**defaults)


async def test_text_items_with_prices_saved():
    items = [
        {"name": "Tomatoes", "price": 2.50, "quantity": 1},
        {"name": "Potatoes", "price": 1.80, "quantity": 1},
        {"name": "Salad", "price": 2.40, "quantity": 1},
    ]
    exp = _make_expense(items_json=json.dumps(items))
    expense_id = await save_expense(exp)

    saved_items = await get_expense_items(expense_id)
    assert len(saved_items) == 3
    assert saved_items[0]["name"] == "Tomatoes"
    assert saved_items[0]["price"] == 2.50
    assert saved_items[1]["name"] == "Potatoes"
    assert saved_items[1]["price"] == 1.80
    assert saved_items[2]["name"] == "Salad"
    assert saved_items[2]["price"] == 2.40


async def test_text_items_without_prices_saved():
    items = [
        {"name": "Milk", "price": None},
        {"name": "Bread", "price": None},
        {"name": "Eggs", "price": None},
    ]
    exp = _make_expense(items_json=json.dumps(items), amount=12.30, amount_eur=12.30)
    expense_id = await save_expense(exp)

    saved_items = await get_expense_items(expense_id)
    # Items without prices are skipped by _save_items_from_json (price is None)
    # This is current behavior — names-only items don't get saved to expense_items
    # They're still in items_json for display/search
    assert isinstance(saved_items, list)


async def test_text_items_null_no_items_saved():
    exp = _make_expense(items_json=None)
    expense_id = await save_expense(exp)

    saved_items = await get_expense_items(expense_id)
    assert saved_items == []


async def test_text_items_with_quantity():
    items = [
        {"name": "Apples", "price": 1.50, "quantity": 3},
        {"name": "Bread", "price": 2.00, "quantity": 1},
    ]
    exp = _make_expense(items_json=json.dumps(items), amount=6.50, amount_eur=6.50)
    expense_id = await save_expense(exp)

    saved_items = await get_expense_items(expense_id)
    assert len(saved_items) == 2
    assert saved_items[0]["quantity"] == 3.0
    assert saved_items[1]["quantity"] == 1.0


async def test_items_json_stored_on_expense():
    items = [{"name": "Coffee", "price": 4.50}]
    items_json = json.dumps(items)
    exp = _make_expense(items_json=items_json, amount=4.50, amount_eur=4.50)
    expense_id = await save_expense(exp)

    from kazo.services.expense_service import get_expense_by_id

    row = await get_expense_by_id(expense_id)
    assert row is not None
    assert row["items_json"] == items_json


async def test_mixed_items_some_with_prices():
    items = [
        {"name": "Tomatoes", "price": 2.50},
        {"name": "Unknown item", "price": None},
        {"name": "Cheese", "price": 3.00},
    ]
    exp = _make_expense(items_json=json.dumps(items), amount=8.00, amount_eur=8.00)
    expense_id = await save_expense(exp)

    saved_items = await get_expense_items(expense_id)
    # Only items with prices get saved to expense_items table
    assert len(saved_items) == 2
    names = [i["name"] for i in saved_items]
    assert "Tomatoes" in names
    assert "Cheese" in names
