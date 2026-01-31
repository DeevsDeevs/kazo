from datetime import date

from kazo.db.database import get_db
from kazo.services.budget_service import (
    budget_vs_actual,
    get_all_budgets,
    get_budget,
    remove_budget,
    set_budget,
)

CHAT = 100


async def _add_expense(chat_id, amount_base, category, expense_date):
    db = await get_db()
    await db.execute(
        """INSERT INTO expenses (chat_id, user_id, store, amount, original_currency,
        amount_base, exchange_rate, category, source, expense_date)
        VALUES (?, 1, 'test', ?, 'EUR', ?, 1.0, ?, 'text', ?)""",
        (chat_id, amount_base, amount_base, category, expense_date),
    )
    await db.commit()


async def test_set_and_get_budget():
    b = await set_budget(CHAT, 2000.0)
    assert b.amount_base == 2000.0
    assert b.category is None

    got = await get_budget(CHAT)
    assert got is not None
    assert got.amount_base == 2000.0


async def test_set_category_budget():
    await set_budget(CHAT, 500.0, "groceries")
    got = await get_budget(CHAT, "groceries")
    assert got is not None
    assert got.amount_base == 500.0


async def test_upsert_budget():
    await set_budget(CHAT, 1000.0)
    await set_budget(CHAT, 2000.0)
    got = await get_budget(CHAT)
    assert got.amount_base == 2000.0


async def test_get_all_budgets():
    await set_budget(CHAT, 2000.0)
    await set_budget(CHAT, 500.0, "groceries")
    await set_budget(CHAT, 300.0, "dining")
    all_b = await get_all_budgets(CHAT)
    assert len(all_b) == 3


async def test_remove_budget():
    await set_budget(CHAT, 2000.0)
    assert await remove_budget(CHAT) is True
    assert await get_budget(CHAT) is None


async def test_remove_nonexistent():
    assert await remove_budget(CHAT) is False


async def test_budget_vs_actual():
    await set_budget(CHAT, 2000.0)
    await set_budget(CHAT, 500.0, "groceries")

    today = date.today()
    start = today.replace(day=1)
    await _add_expense(CHAT, 100.0, "groceries", today.isoformat())
    await _add_expense(CHAT, 200.0, "dining", today.isoformat())

    data = await budget_vs_actual(CHAT, start, today)
    assert len(data) == 2

    total_entry = next(d for d in data if d["category"] is None)
    assert total_entry["spent"] == 300.0
    assert total_entry["remaining"] == 1700.0

    groceries_entry = next(d for d in data if d["category"] == "groceries")
    assert groceries_entry["spent"] == 100.0
    assert groceries_entry["remaining"] == 400.0


async def test_budget_vs_actual_empty():
    result = await budget_vs_actual(CHAT, date.today(), date.today())
    assert result == []
