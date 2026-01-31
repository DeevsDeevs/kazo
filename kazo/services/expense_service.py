import json
from datetime import date, timedelta

from kazo.db.database import get_db
from kazo.db.models import Expense


async def save_expense(expense: Expense) -> int:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO expenses
        (chat_id, user_id, store, amount, original_currency, amount_eur,
         exchange_rate, category, items_json, source, expense_date, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            expense.chat_id,
            expense.user_id,
            expense.store,
            expense.amount,
            expense.original_currency,
            expense.amount_eur,
            expense.exchange_rate,
            expense.category,
            expense.items_json,
            expense.source,
            expense.expense_date,
            expense.note,
        ),
    )
    await db.commit()
    assert cursor.lastrowid is not None
    expense_id = cursor.lastrowid
    if expense.items_json:
        await _save_items_from_json(db, expense_id, expense.items_json, expense.original_currency)
    return expense_id


async def get_expenses(
    chat_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict]:
    db = await get_db()
    query = "SELECT * FROM expenses WHERE chat_id = ?"
    params: list[int | str] = [chat_id]
    if start_date:
        query += " AND expense_date >= ?"
        params.append(start_date.isoformat())
    if end_date:
        query += " AND expense_date <= ?"
        params.append(end_date.isoformat())
    query += " ORDER BY expense_date DESC"
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_expense_by_id(expense_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def update_expense(expense_id: int, **fields) -> bool:
    if not fields:
        return False
    allowed = {
        "store",
        "amount",
        "original_currency",
        "amount_eur",
        "exchange_rate",
        "category",
        "description",
        "expense_date",
        "note",
    }
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return False
    db = await get_db()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = [*fields.values(), expense_id]
    cursor = await db.execute(f"UPDATE expenses SET {set_clause} WHERE id = ?", values)
    await db.commit()
    return cursor.rowcount > 0


async def link_bot_message(chat_id: int, bot_message_id: int, expense_id: int):
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO bot_message_expenses (bot_message_id, chat_id, expense_id) VALUES (?, ?, ?)",
        (bot_message_id, chat_id, expense_id),
    )
    await db.commit()


async def get_expense_by_bot_message(chat_id: int, bot_message_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        """SELECT e.* FROM expenses e
           JOIN bot_message_expenses bme ON e.id = bme.expense_id
           WHERE bme.chat_id = ? AND bme.bot_message_id = ?""",
        (chat_id, bot_message_id),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_last_expense(chat_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM expenses WHERE chat_id = ? ORDER BY id DESC LIMIT 1",
        (chat_id,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def delete_last_expense(chat_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM expenses WHERE chat_id = ? ORDER BY id DESC LIMIT 1",
        (chat_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return None
    expense = dict(row)
    await db.execute("DELETE FROM expenses WHERE id = ?", (expense["id"],))
    await db.commit()
    return expense


async def _save_items_from_json(db, expense_id: int, items_json: str, currency: str):
    try:
        items = json.loads(items_json)
    except (json.JSONDecodeError, TypeError):
        return
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("item")
        price = item.get("price")
        if price is None:
            price = item.get("amount")
        if not name or price is None:
            continue
        try:
            price = float(price)
            quantity = float(item.get("quantity", 1))
        except (ValueError, TypeError):
            continue
        item_currency = item.get("currency", currency)
        await db.execute(
            "INSERT INTO expense_items (expense_id, name, price, currency, quantity) VALUES (?, ?, ?, ?, ?)",
            (expense_id, str(name), price, item_currency, quantity),
        )
    await db.commit()


async def save_expense_items(expense_id: int, items: list[dict], currency: str):
    db = await get_db()
    await db.execute("DELETE FROM expense_items WHERE expense_id = ?", (expense_id,))
    for item in items:
        name = item.get("name") or item.get("item", "")
        try:
            price = float(item.get("price", 0))
            quantity = float(item.get("quantity", 1))
        except (ValueError, TypeError):
            continue
        item_currency = item.get("currency", currency)
        await db.execute(
            "INSERT INTO expense_items (expense_id, name, price, currency, quantity) VALUES (?, ?, ?, ?, ?)",
            (expense_id, name, price, item_currency, quantity),
        )
    await db.commit()


async def get_expense_items(expense_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM expense_items WHERE expense_id = ? ORDER BY id",
        (expense_id,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def search_items_by_name(name: str, chat_id: int | None = None) -> list[dict]:
    db = await get_db()
    query = """
        SELECT ei.*, e.store, e.expense_date, e.chat_id
        FROM expense_items ei
        JOIN expenses e ON ei.expense_id = e.id
        WHERE ei.name LIKE ?
    """
    params: list = [f"%{name}%"]
    if chat_id is not None:
        query += " AND e.chat_id = ?"
        params.append(chat_id)
    query += " ORDER BY e.expense_date DESC"
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def detect_recurring(chat_id: int, store: str, amount_eur: float) -> bool:
    """Check if same store + similar amount (±20%) appeared 2+ times in last 3 months."""
    if not store:
        return False
    db = await get_db()
    three_months_ago = (date.today() - timedelta(days=90)).isoformat()
    low = amount_eur * 0.8
    high = amount_eur * 1.2
    cursor = await db.execute(
        """SELECT COUNT(*) FROM expenses
           WHERE chat_id = ? AND store = ? AND amount_eur BETWEEN ? AND ?
           AND expense_date >= ?""",
        (chat_id, store, low, high, three_months_ago),
    )
    row = await cursor.fetchone()
    return row[0] >= 2


async def migrate_items_json():
    db = await get_db()
    cursor = await db.execute("SELECT id, items_json, original_currency FROM expenses WHERE items_json IS NOT NULL")
    rows = await cursor.fetchall()
    for row in rows:
        existing = await db.execute("SELECT 1 FROM expense_items WHERE expense_id = ? LIMIT 1", (row[0],))
        if await existing.fetchone():
            continue
        await _save_items_from_json(db, row[0], row[1], row[2])
