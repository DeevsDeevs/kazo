from datetime import date

from kazo.db.database import get_db
from kazo.db.models import Budget


async def set_budget(chat_id: int, amount_base: float, category: str | None = None) -> Budget:
    db = await get_db()
    await db.execute(
        "DELETE FROM budgets WHERE chat_id = ? AND category IS ?",
        (chat_id, category),
    )
    await db.execute(
        "INSERT INTO budgets (chat_id, category, amount_base) VALUES (?, ?, ?)",
        (chat_id, category, amount_base),
    )
    await db.commit()
    return Budget(id=None, chat_id=chat_id, category=category, amount_base=amount_base)


async def get_budget(chat_id: int, category: str | None = None) -> Budget | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM budgets WHERE chat_id = ? AND category IS ?",
        (chat_id, category),
    )
    row = await cursor.fetchone()
    if row:
        return Budget(**dict(row))
    return None


async def get_all_budgets(chat_id: int) -> list[Budget]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM budgets WHERE chat_id = ? ORDER BY category",
        (chat_id,),
    )
    rows = await cursor.fetchall()
    return [Budget(**dict(row)) for row in rows]


async def remove_budget(chat_id: int, category: str | None = None) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM budgets WHERE chat_id = ? AND category IS ?",
        (chat_id, category),
    )
    await db.commit()
    return cursor.rowcount > 0


async def budget_vs_actual(chat_id: int, start_date: date, end_date: date) -> list[dict]:
    db = await get_db()
    budgets = await get_all_budgets(chat_id)
    if not budgets:
        return []

    result = []
    for b in budgets:
        if b.category is None:
            cursor = await db.execute(
                """SELECT COALESCE(SUM(amount_base), 0) as spent
                FROM expenses WHERE chat_id = ? AND expense_date >= ? AND expense_date <= ?""",
                (chat_id, start_date.isoformat(), end_date.isoformat()),
            )
        else:
            cursor = await db.execute(
                """SELECT COALESCE(SUM(amount_base), 0) as spent
                FROM expenses WHERE chat_id = ? AND category = ?
                AND expense_date >= ? AND expense_date <= ?""",
                (chat_id, b.category, start_date.isoformat(), end_date.isoformat()),
            )
        row = await cursor.fetchone()
        spent = row["spent"]
        result.append(
            {
                "category": b.category,
                "budget": b.amount_base,
                "spent": spent,
                "remaining": b.amount_base - spent,
                "pct": (spent / b.amount_base * 100) if b.amount_base > 0 else 0,
            }
        )
    return result
