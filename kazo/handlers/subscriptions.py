import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from kazo.services.currency_service import convert_to_eur
from kazo.services.subscription_service import (
    add_subscription,
    get_subscriptions,
    refresh_subscription_rates,
    remove_subscription,
)

logger = logging.getLogger(__name__)
router = Router()

VALID_FREQUENCIES = {"daily", "weekly", "monthly", "yearly"}


def _to_monthly(amount: float, frequency: str) -> float:
    if frequency == "yearly":
        return amount / 12
    if frequency == "weekly":
        return amount * 4.33
    if frequency == "daily":
        return amount * 30.44
    return amount


@router.message(Command("subs"))
async def cmd_subs(message: Message):
    await refresh_subscription_rates(message.chat.id)
    subs = await get_subscriptions(message.chat.id)
    if not subs:
        await message.answer("No active subscriptions. Use /addsub to add one.")
        return

    total_monthly = sum(_to_monthly(s["amount_eur"], s["frequency"]) for s in subs)
    lines = []
    for s in subs:
        currency_note = f" ({s['amount']} {s['original_currency']})" if s["original_currency"] != "EUR" else ""
        lines.append(f"• {s['name']}: €{s['amount_eur']:.2f}{currency_note} ({s['frequency']})")

    await message.answer(
        "📋 Active subscriptions:\n"
        + "\n".join(lines)
        + f"\n\nTotal: ~€{total_monthly:.2f}/month"
    )


@router.message(Command("addsub"))
async def cmd_addsub(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /addsub Netflix 15.99 EUR monthly")
        return

    args = parts[1].split()
    if len(args) < 2:
        await message.answer("Usage: /addsub Netflix 15.99 EUR monthly")
        return

    name = args[0]
    try:
        amount = float(args[1])
    except ValueError:
        await message.answer("Invalid amount. Usage: /addsub Netflix 15.99 EUR monthly")
        return

    currency = args[2].upper() if len(args) > 2 else "EUR"
    frequency = args[3].lower() if len(args) > 3 else "monthly"

    if frequency not in VALID_FREQUENCIES:
        await message.answer(f"Invalid frequency. Choose from: {', '.join(sorted(VALID_FREQUENCIES))}")
        return

    amount_eur, _ = await convert_to_eur(amount, currency)

    await add_subscription(
        chat_id=message.chat.id,
        name=name,
        amount=amount,
        currency=currency,
        amount_eur=amount_eur,
        frequency=frequency,
        category="subscriptions",
    )

    await message.answer(f"Added subscription: {name} €{amount_eur:.2f}/{frequency}")


@router.message(Command("removesub"))
async def cmd_removesub(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /removesub Netflix")
        return

    name = parts[1].strip()
    removed = await remove_subscription(message.chat.id, name)

    if removed:
        await message.answer(f"Removed subscription: {name}")
    else:
        await message.answer(f"Subscription '{name}' not found.")
