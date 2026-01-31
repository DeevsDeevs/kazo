import logging

from kazo.db.database import get_db
from kazo.services.currency_service import convert_to_eur

logger = logging.getLogger(__name__)


async def refresh_subscription_rates(chat_id: int) -> None:
    """Re-convert non-EUR subscriptions using current exchange rates."""
    subs = await get_subscriptions(chat_id)
    db = await get_db()
    for s in subs:
        if s["original_currency"] == "EUR":
            continue
        try:
            new_eur, _ = await convert_to_eur(s["amount"], s["original_currency"])
            if new_eur != s["amount_eur"]:
                await db.execute(
                    "UPDATE subscriptions SET amount_eur = ? WHERE id = ?",
                    (new_eur, s["id"]),
                )
                logger.debug(
                    "Updated %s rate: €%.2f -> €%.2f",
                    s["name"], s["amount_eur"], new_eur,
                )
        except Exception:
            logger.warning("Failed to refresh rate for %s", s["name"])
    await db.commit()


async def get_subscriptions(chat_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM subscriptions WHERE chat_id = ? AND active = 1 ORDER BY name",
        (chat_id,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def add_subscription(
    chat_id: int, name: str, amount: float, currency: str,
    amount_eur: float, frequency: str = "monthly", category: str | None = None,
) -> int:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO subscriptions
        (chat_id, name, amount, original_currency, amount_eur, frequency, category)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (chat_id, name, amount, currency, amount_eur, frequency, category),
    )
    await db.commit()
    return cursor.lastrowid


async def remove_subscription(chat_id: int, name: str) -> bool:
    db = await get_db()
    cursor = await db.execute(
        "UPDATE subscriptions SET active = 0 WHERE chat_id = ? AND LOWER(name) = LOWER(?) AND active = 1",
        (chat_id, name),
    )
    await db.commit()
    return cursor.rowcount > 0
