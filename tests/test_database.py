import aiosqlite


async def test_schema_creates_tables(test_db: aiosqlite.Connection):
    cursor = await test_db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in await cursor.fetchall()]
    assert "expenses" in tables
    assert "subscriptions" in tables
    assert "exchange_rates" in tables
    assert "custom_categories" in tables


async def test_expense_check_constraint(test_db: aiosqlite.Connection):
    import sqlite3

    import pytest

    with pytest.raises(sqlite3.IntegrityError):
        await test_db.execute(
            "INSERT INTO expenses (chat_id, user_id, amount, original_currency, "
            "amount_base, exchange_rate, source, expense_date) "
            "VALUES (1, 1, -5, 'EUR', -5, 1.0, 'text', '2025-01-01')"
        )


async def test_subscription_frequency_check(test_db: aiosqlite.Connection):
    import sqlite3

    import pytest

    with pytest.raises(sqlite3.IntegrityError):
        await test_db.execute(
            "INSERT INTO subscriptions (chat_id, name, amount, original_currency, "
            "amount_base, frequency) VALUES (1, 'test', 10, 'EUR', 10, 'biweekly')"
        )
