import json
from datetime import date

from kazo.db.models import Expense
from kazo.services.expense_service import save_expense, search_items_by_name


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


async def test_price_history_multiple_dates():
    for d in [date(2025, 1, 10), date(2025, 2, 15), date(2025, 3, 20)]:
        items = [{"name": "Tomatoes", "price": 3.50 + d.month * 0.1}]
        await save_expense(_make_expense(items_json=json.dumps(items), expense_date=d))

    results = await search_items_by_name("Tomatoes", chat_id=1)
    assert len(results) == 3
    # Ordered by expense_date DESC
    assert results[0]["expense_date"] >= results[1]["expense_date"]


async def test_price_history_store_filter():
    items = [{"name": "Bread", "price": 2.0}]
    await save_expense(_make_expense(items_json=json.dumps(items), store="Lidl"))
    await save_expense(_make_expense(items_json=json.dumps(items), store="Aldi"))

    results = await search_items_by_name("Bread", chat_id=1)
    assert len(results) == 2

    lidl_only = [r for r in results if "lidl" in r["store"].lower()]
    assert len(lidl_only) == 1


async def test_price_fuzzy_match():
    items = [{"name": "Cherry Tomatoes", "price": 4.0}]
    await save_expense(_make_expense(items_json=json.dumps(items)))

    results = await search_items_by_name("tomato", chat_id=1)
    assert len(results) == 1
    assert results[0]["name"] == "Cherry Tomatoes"


async def test_compare_across_stores():
    for store, price in [("Lidl", 2.0), ("Lidl", 2.5), ("Aldi", 3.0)]:
        items = [{"name": "Milk", "price": price}]
        await save_expense(_make_expense(items_json=json.dumps(items), store=store))

    results = await search_items_by_name("Milk", chat_id=1)
    stores: dict[str, list[float]] = {}
    for r in results:
        stores.setdefault(r["store"], []).append(r["price"])

    assert "Lidl" in stores
    assert "Aldi" in stores
    assert len(stores["Lidl"]) == 2
    lidl_avg = sum(stores["Lidl"]) / len(stores["Lidl"])
    assert lidl_avg == 2.25


async def test_items_empty_chat():
    results = await search_items_by_name("anything", chat_id=999)
    assert results == []
