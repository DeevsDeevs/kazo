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


async def all_time_stats(chat_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        """SELECT COUNT(*) as count, COALESCE(SUM(amount_eur), 0) as total,
                  COALESCE(AVG(amount_eur), 0) as avg_expense,
                  COALESCE(MAX(amount_eur), 0) as max_expense,
                  MIN(expense_date) as first_date, MAX(expense_date) as last_date
        FROM expenses WHERE chat_id = ?""",
        (chat_id,),
    )
    row = await cursor.fetchone()
    if not row or row["count"] == 0:
        return None
    stats = dict(row)

    cursor = await db.execute(
        """SELECT category, SUM(amount_eur) as total
        FROM expenses WHERE chat_id = ?
        GROUP BY category ORDER BY total DESC LIMIT 5""",
        (chat_id,),
    )
    stats["top_categories"] = [dict(r) for r in await cursor.fetchall()]

    cursor = await db.execute(
        """SELECT store, SUM(amount_eur) as total, COUNT(*) as count
        FROM expenses WHERE chat_id = ? AND store IS NOT NULL
        GROUP BY store ORDER BY total DESC LIMIT 5""",
        (chat_id,),
    )
    stats["top_stores"] = [dict(r) for r in await cursor.fetchall()]

    cursor = await db.execute(
        """SELECT strftime('%Y-%m', expense_date) as month, SUM(amount_eur) as total
        FROM expenses WHERE chat_id = ?
        GROUP BY month ORDER BY month DESC LIMIT 2""",
        (chat_id,),
    )
    stats["monthly_comparison"] = [dict(r) for r in await cursor.fetchall()]

    return stats


async def search_expenses(
    chat_id: int, query: str, start_date: date | None = None, end_date: date | None = None
) -> list[dict]:
    db = await get_db()
    sql = """SELECT * FROM expenses
             WHERE chat_id = ? AND (
                 store LIKE ? OR category LIKE ? OR items_json LIKE ? OR note LIKE ?
             )"""
    params: list = [chat_id, f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"]
    if start_date:
        sql += " AND expense_date >= ?"
        params.append(start_date.isoformat())
    if end_date:
        sql += " AND expense_date <= ?"
        params.append(end_date.isoformat())
    sql += " ORDER BY expense_date DESC LIMIT 20"
    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
