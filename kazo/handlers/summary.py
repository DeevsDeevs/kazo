import logging
from datetime import date, timedelta
from pathlib import Path

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile

from kazo.charts import spending_by_category_chart, monthly_trend_chart, daily_spending_chart
from kazo.services.summary_service import spending_by_category, monthly_totals, daily_spending

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("summary"))
async def cmd_summary(message: Message):
    today = date.today()
    start = today.replace(day=1)

    data = await spending_by_category(message.chat.id, start, today)

    if not data:
        await message.answer("No expenses this month yet.")
        return

    total = sum(row["total"] for row in data)
    lines = [f"• {row['category'] or 'uncategorized'}: €{row['total']:.2f} ({row['count']} items)" for row in data]

    text = (
        f"📊 Summary for {today.strftime('%B %Y')}\n\n"
        + "\n".join(lines)
        + f"\n\nTotal: €{total:.2f}"
    )

    chart_path = await spending_by_category_chart(data)
    if chart_path:
        try:
            await message.answer_photo(FSInputFile(chart_path), caption=text)
        finally:
            Path(chart_path).unlink(missing_ok=True)
    else:
        await message.answer(text)


@router.message(Command("monthly"))
async def cmd_monthly(message: Message):
    data = await monthly_totals(message.chat.id, months=6)

    if not data:
        await message.answer("No expense history yet.")
        return

    lines = [f"• {row['month']}: €{row['total']:.2f} ({row['count']} items)" for row in reversed(data)]

    text = "📈 Monthly spending:\n\n" + "\n".join(lines)

    chart_path = await monthly_trend_chart(list(reversed(data)))
    if chart_path:
        try:
            await message.answer_photo(FSInputFile(chart_path), caption=text)
        finally:
            Path(chart_path).unlink(missing_ok=True)
    else:
        await message.answer(text)


@router.message(Command("daily"))
async def cmd_daily(message: Message) -> None:
    today = date.today()
    start = today - timedelta(days=29)

    data = await daily_spending(message.chat.id, start, today)

    if not data:
        await message.answer("No expenses in the last 30 days.")
        return

    total = sum(row["total"] for row in data)
    avg = total / 30
    text = (
        f"Daily spending (last 30 days)\n\n"
        f"Total: \u20ac{total:,.2f}\n"
        f"Daily avg: \u20ac{avg:,.2f}"
    )

    chart_path = await daily_spending_chart(data)
    if chart_path:
        try:
            await message.answer_photo(FSInputFile(chart_path), caption=text)
        finally:
            Path(chart_path).unlink(missing_ok=True)
    else:
        await message.answer(text)
