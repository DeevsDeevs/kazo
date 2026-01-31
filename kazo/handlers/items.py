import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from kazo.currency import get_base_currency
from kazo.services.expense_service import search_items_by_name

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("price"))
async def cmd_price(message: Message):
    parts = message.text.strip().split(maxsplit=1)
    args = parts[1] if len(parts) > 1 else ""
    if not args:
        await message.reply("Usage: /price <item name> [store]\nExample: /price tomatoes lidl")
        return

    parts = args.rsplit(" ", 1)
    item_name = args
    store_filter = None

    results = await search_items_by_name(item_name, chat_id=message.chat.id)

    if not results and len(parts) == 2:
        item_name = parts[0]
        store_filter = parts[1]
        results = await search_items_by_name(item_name, chat_id=message.chat.id)

    if store_filter:
        results = [r for r in results if r.get("store") and store_filter.lower() in r["store"].lower()]

    if not results:
        await message.reply(f'No price history found for "{args}".')
        return

    prices = [r["price"] * r.get("quantity", 1) for r in results if r.get("price") is not None]
    if not prices:
        await message.reply(f'No priced records found for "{args}".')
        return
    min_p, max_p, avg_p = min(prices), max(prices), sum(prices) / len(prices)
    base = await get_base_currency(message.chat.id)
    currency = results[0].get("currency", base)

    lines = [f'📊 Price history for "{item_name}" ({len(results)} records)']
    lines.append(f"Min: {min_p:.2f} {currency} | Avg: {avg_p:.2f} {currency} | Max: {max_p:.2f} {currency}")
    lines.append("")

    for r in results[:10]:
        store = r.get("store") or "?"
        date = r.get("expense_date", "?")
        price = r.get("price")
        qty = r.get("quantity", 1)
        if price is None:
            continue
        line = f"  {date} — {price:.2f} {currency}"
        if qty != 1:
            line += f" x{qty:.0f}"
        line += f" @ {store}"
        lines.append(line)

    if len(results) > 10:
        lines.append(f"  ... and {len(results) - 10} more")

    await message.reply("\n".join(lines))


@router.message(Command("items"))
async def cmd_items(message: Message):
    parts = message.text.strip().split(maxsplit=1)
    args = parts[1] if len(parts) > 1 else ""

    from kazo.db.database import get_db

    db = await get_db()

    if args:
        cursor = await db.execute(
            """SELECT ei.name, ei.price, ei.currency, e.store, e.expense_date
               FROM expense_items ei
               JOIN expenses e ON ei.expense_id = e.id
               WHERE e.chat_id = ? AND e.category LIKE ?
               ORDER BY e.expense_date DESC LIMIT 30""",
            (message.chat.id, f"%{args}%"),
        )
    else:
        cursor = await db.execute(
            """SELECT ei.name, ei.price, ei.currency, e.store, e.expense_date
               FROM expense_items ei
               JOIN expenses e ON ei.expense_id = e.id
               WHERE e.chat_id = ?
               ORDER BY e.expense_date DESC LIMIT 30""",
            (message.chat.id,),
        )

    rows = await cursor.fetchall()
    if not rows:
        await message.reply("No items found." + (f" (category: {args})" if args else ""))
        return

    lines = ["📋 Recent items" + (f" ({args})" if args else "") + ":"]
    for r in rows:
        r = dict(r)
        price = r.get("price")
        if price is None:
            continue
        lines.append(f"  {r['name']} — {price:.2f} {r['currency']} @ {r.get('store') or '?'} ({r['expense_date']})")

    await message.reply("\n".join(lines))


@router.message(Command("compare"))
async def cmd_compare(message: Message):
    parts = message.text.strip().split(maxsplit=1)
    args = parts[1] if len(parts) > 1 else ""
    if not args:
        await message.reply("Usage: /compare <item name>\nExample: /compare tomatoes")
        return

    results = await search_items_by_name(args, chat_id=message.chat.id)
    if not results:
        await message.reply(f'No records found for "{args}".')
        return

    stores: dict[str, list[float]] = {}
    for r in results:
        store = r.get("store") or "Unknown"
        if r.get("price") is None:
            continue
        stores.setdefault(store, []).append(r["price"])

    sorted_stores = sorted(stores.items(), key=lambda x: sum(x[1]) / len(x[1]))
    base = await get_base_currency(message.chat.id)
    currency = results[0].get("currency", base)

    lines = [f'🏪 Price comparison for "{args}":']
    for store, prices in sorted_stores:
        avg = sum(prices) / len(prices)
        lines.append(f"  {store}: avg {avg:.2f} {currency} ({len(prices)} purchases)")

    await message.reply("\n".join(lines))
