import logging
from datetime import date

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from kazo.currency import format_amount, get_base_currency
from kazo.services.currency_service import convert_to_base
from kazo.services.subscription_service import (
    add_subscription,
    get_subscriptions,
    refresh_subscription_rates,
    remove_subscription,
)

logger = logging.getLogger(__name__)
router = Router()

VALID_FREQUENCIES = {"daily", "weekly", "monthly", "yearly"}


def _next_billing_date(billing_day: int, frequency: str) -> date:
    today = date.today()
    if frequency == "yearly":
        # billing_day treated as day of current/next month
        pass
    if frequency in ("monthly", "yearly"):
        import calendar

        year, month = today.year, today.month
        max_day = calendar.monthrange(year, month)[1]
        day = min(billing_day, max_day)
        candidate = date(year, month, day)
        if candidate <= today:
            month += 1
            if month > 12:
                month = 1
                year += 1
            max_day = calendar.monthrange(year, month)[1]
            day = min(billing_day, max_day)
            candidate = date(year, month, day)
        return candidate
    return today


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

    base = await get_base_currency(message.chat.id)
    total_monthly = sum(_to_monthly(s["amount_base"], s["frequency"]) for s in subs)
    lines = []
    for s in subs:
        currency_note = f" ({s['amount']} {s['original_currency']})" if s["original_currency"] != base else ""
        billing_info = ""
        if s.get("billing_day") and s["frequency"] in ("monthly", "yearly"):
            next_date = _next_billing_date(s["billing_day"], s["frequency"])
            days_until = (next_date - date.today()).days
            billing_info = f" — next: {next_date.strftime('%b %d')} ({days_until}d)"
        lines.append(
            f"• {s['name']}: {format_amount(s['amount_base'], base)}{currency_note} ({s['frequency']}){billing_info}"
        )

    await message.answer(
        "📋 Active subscriptions:\n" + "\n".join(lines) + f"\n\nTotal: ~{format_amount(total_monthly, base)}/month"
    )


@router.message(Command("addsub"))
async def cmd_addsub(message: Message):
    base = await get_base_currency(message.chat.id)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(f"Usage: /addsub Netflix 15.99 {base} monthly [day]")
        return

    args = parts[1].split()
    if len(args) < 2:
        await message.answer(f"Usage: /addsub Netflix 15.99 {base} monthly [day]")
        return

    name = args[0]
    try:
        amount = float(args[1])
    except ValueError:
        await message.answer(f"Invalid amount. Usage: /addsub Netflix 15.99 {base} monthly")
        return

    currency = args[2].upper() if len(args) > 2 else base
    frequency = args[3].lower() if len(args) > 3 else "monthly"

    if frequency not in VALID_FREQUENCIES:
        await message.answer(f"Invalid frequency. Choose from: {', '.join(sorted(VALID_FREQUENCIES))}")
        return

    billing_day = None
    if len(args) > 4:
        try:
            billing_day = int(args[4])
            if not 1 <= billing_day <= 31:
                await message.answer("Billing day must be between 1 and 31.")
                return
        except ValueError:
            await message.answer("Billing day must be a number (1-31).")
            return

    amount_base, _ = await convert_to_base(amount, currency, message.chat.id)

    await add_subscription(
        chat_id=message.chat.id,
        name=name,
        amount=amount,
        currency=currency,
        amount_base=amount_base,
        frequency=frequency,
        category="subscriptions",
        billing_day=billing_day,
    )

    day_info = f" (bills on day {billing_day})" if billing_day else ""
    await message.answer(f"Added subscription: {name} {format_amount(amount_base, base)}/{frequency}{day_info}")


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
