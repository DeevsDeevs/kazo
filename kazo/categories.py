from sqlite3 import IntegrityError

from kazo.db.database import get_db

DEFAULT_CATEGORIES: list[str] = [
    "groceries",
    "dining",
    "transport",
    "utilities",
    "entertainment",
    "healthcare",
    "shopping",
    "subscriptions",
    "housing",
    "education",
    "travel",
    "personal",
    "gifts",
    "other",
]


async def get_custom_categories(chat_id: int) -> list[str]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT name FROM custom_categories WHERE chat_id = ? ORDER BY name",
        (chat_id,),
    )
    rows = await cursor.fetchall()
    return [row[0] for row in rows]


async def get_categories(chat_id: int) -> list[str]:
    custom = await get_custom_categories(chat_id)
    return DEFAULT_CATEGORIES + custom


async def get_categories_str(chat_id: int) -> str:
    return ", ".join(await get_categories(chat_id))


async def add_category(chat_id: int, name: str) -> bool:
    """Add a custom category. Returns False if it already exists."""
    normalized = name.strip().lower()
    if normalized in DEFAULT_CATEGORIES:
        return False
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO custom_categories (chat_id, name) VALUES (?, ?)",
            (chat_id, normalized),
        )
        await db.commit()
    except Exception:
        return False
    return True


async def remove_category(chat_id: int, name: str) -> bool:
    """Remove a custom category. Returns False if it's a default or doesn't exist."""
    normalized = name.strip().lower()
    if normalized in DEFAULT_CATEGORIES:
        return False
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM custom_categories WHERE chat_id = ? AND name = ?",
        (chat_id, normalized),
    )
    await db.commit()
    return cursor.rowcount > 0
