from datetime import date

from kazo.db.database import get_db
from kazo.db.models import Expense


async def save_expense(expense: Expense) -> int:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO expenses
        (chat_id, user_id, store, amount, original_currency, amount_eur,
         exchange_rate, category, items_json, source, expense_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            expense.chat_id, expense.user_id, expense.store,
            expense.amount, expense.original_currency, expense.amount_eur,
            expense.exchange_rate, expense.category, expense.items_json,
            expense.source, expense.expense_date.isoformat(),
        ),
    )
    await db.commit()
    assert cursor.lastrowid is not None
    return cursor.lastrowid


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
