from datetime import date

from kazo.db.database import get_db


async def spending_by_category(chat_id: int, start_date: date, end_date: date) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT category, SUM(amount_eur) as total, COUNT(*) as count
        FROM expenses
        WHERE chat_id = ? AND expense_date >= ? AND expense_date <= ?
        GROUP BY category ORDER BY total DESC""",
        (chat_id, start_date.isoformat(), end_date.isoformat()),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def monthly_totals(chat_id: int, months: int = 6) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT strftime('%Y-%m', expense_date) as month,
                  SUM(amount_eur) as total, COUNT(*) as count
        FROM expenses
        WHERE chat_id = ?
        GROUP BY month ORDER BY month DESC LIMIT ?""",
        (chat_id, months),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def daily_spending(chat_id: int, start_date: date, end_date: date) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT expense_date, SUM(amount_eur) as total, COUNT(*) as count
        FROM expenses
        WHERE chat_id = ? AND expense_date >= ? AND expense_date <= ?
        GROUP BY expense_date ORDER BY expense_date""",
        (chat_id, start_date.isoformat(), end_date.isoformat()),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
