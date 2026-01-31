import logging

from kazo.currency import get_base_currency
from kazo.db.database import get_db
from kazo.services.currency_service import convert_to_base

logger = logging.getLogger(__name__)


async def refresh_subscription_rates(chat_id: int) -> None:
    """Re-convert non-base-currency subscriptions using current exchange rates."""
    base = await get_base_currency(chat_id)
    subs = await get_subscriptions(chat_id)
    db = await get_db()
    for s in subs:
        if s["original_currency"] == base:
            continue
        try:
            new_amount, _ = await convert_to_base(s["amount"], s["original_currency"], chat_id)
            if new_amount != s["amount_base"]:
                await db.execute(
                    "UPDATE subscriptions SET amount_base = ? WHERE id = ?",
                    (new_amount, s["id"]),
                )
                logger.debug(
                    "Updated %s rate: %.2f -> %.2f %s",
                    s["name"],
                    s["amount_base"],
                    new_amount,
                    base,
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
    chat_id: int,
    name: str,
    amount: float,
    currency: str,
    amount_base: float,
    frequency: str = "monthly",
    category: str | None = None,
    billing_day: int | None = None,
) -> int:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO subscriptions
        (chat_id, name, amount, original_currency, amount_base, frequency, category, billing_day)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (chat_id, name, amount, currency, amount_base, frequency, category, billing_day),
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
