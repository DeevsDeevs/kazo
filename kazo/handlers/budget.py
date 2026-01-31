import logging
from datetime import date

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from kazo.currency import format_amount, get_base_currency
from kazo.services.budget_service import (
    budget_vs_actual,
    get_all_budgets,
    remove_budget,
    set_budget,
)

logger = logging.getLogger(__name__)
router = Router()


def _progress_bar(pct: float, width: int = 10) -> str:
    filled = min(int(pct / 100 * width), width)
    return "█" * filled + "░" * (width - filled)


@router.message(Command("setbudget"))
async def cmd_setbudget(message: Message):
    parts = message.text.split(maxsplit=2) if message.text else []

    if len(parts) < 2:
        await message.answer(
            "Usage:\n/setbudget 2000 — set monthly total budget\n/setbudget groceries 500 — set category budget"
        )
        return

    if len(parts) == 2:
        try:
            amount = float(parts[1])
        except ValueError:
            await message.answer("Invalid amount. Usage: /setbudget 2000")
            return
        category = None
    else:
        try:
            amount = float(parts[2])
            category = parts[1].lower()
        except ValueError:
            try:
                amount = float(parts[1])
                category = None
            except ValueError:
                await message.answer("Invalid amount. Usage: /setbudget groceries 500")
                return

    if amount <= 0:
        await message.answer("Budget must be positive.")
        return

    base = await get_base_currency(message.chat.id)
    b = await set_budget(message.chat.id, amount, category)
    label = b.category or "Total"
    await message.answer(f"Budget set: {label} → {format_amount(b.amount_eur, base)}/month")


@router.message(Command("removebudget"))
async def cmd_removebudget(message: Message):
    parts = message.text.split(maxsplit=1) if message.text else []
    category = parts[1].lower() if len(parts) > 1 else None

    removed = await remove_budget(message.chat.id, category)
    if removed:
        label = category or "total"
        await message.answer(f"Removed {label} budget.")
    else:
        await message.answer("No matching budget found.")


@router.message(Command("budget"))
async def cmd_budget(message: Message):
    today = date.today()
    start = today.replace(day=1)

    budgets = await get_all_budgets(message.chat.id)
    if not budgets:
        await message.answer("No budgets set. Use /setbudget to create one.")
        return

    data = await budget_vs_actual(message.chat.id, start, today)
    if not data:
        await message.answer("No budget data available.")
        return

    base = await get_base_currency(message.chat.id)
    lines = []
    for d in data:
        label = d["category"] or "Total"
        bar = _progress_bar(d["pct"])
        lines.append(
            f"{label}: {format_amount(d['spent'], base)} / {format_amount(d['budget'], base)}\n"
            f"  {bar} {d['pct']:.0f}%  ({format_amount(d['remaining'], base)} left)"
        )

    text = f"💰 Budget — {today.strftime('%B %Y')}\n\n" + "\n\n".join(lines)
    await message.answer(text)
