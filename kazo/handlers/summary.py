import logging
from datetime import date, timedelta
from pathlib import Path

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from kazo.charts import daily_spending_chart, monthly_trend_chart, spending_by_category_chart
from kazo.currency import format_amount, get_base_currency
from kazo.services.budget_service import budget_vs_actual
from kazo.services.summary_service import (
    all_time_stats,
    daily_spending,
    monthly_totals,
    search_expenses,
    spending_by_category,
)

logger = logging.getLogger(__name__)
router = Router()


def _parse_date_range(arg: str | None) -> tuple[date, date, str] | None:
    today = date.today()
    if not arg:
        return None
    arg = arg.strip().lower()
    if arg == "week":
        start = today - timedelta(days=today.weekday())
        return start, today, "this week"
    if arg == "year":
        return date(today.year, 1, 1), today, str(today.year)
    if arg in ("q1", "q2", "q3", "q4"):
        q = int(arg[1])
        start_month = (q - 1) * 3 + 1
        start = date(today.year, start_month, 1)
        end = date(today.year, start_month + 3, 1) - timedelta(days=1) if q < 4 else date(today.year, 12, 31)
        return start, min(end, today), f"Q{q} {today.year}"
    return None


@router.message(Command("summary"))
async def cmd_summary(message: Message):
    today = date.today()
    parts = message.text.split(maxsplit=1) if message.text else []
    arg = parts[1] if len(parts) > 1 else None

    parsed = _parse_date_range(arg)
    if parsed:
        start, end, label = parsed
    else:
        start = today.replace(day=1)
        end = today
        label = today.strftime("%B %Y")

    data = await spending_by_category(message.chat.id, start, end)

    if not data:
        await message.answer(f"No expenses for {label}.")
        return

    base = await get_base_currency(message.chat.id)
    total = sum(row["total"] for row in data)
    lines = [
        f"• {row['category'] or 'uncategorized'}: {format_amount(row['total'], base)} ({row['count']} items)"
        for row in data
    ]

    text = f"📊 Summary for {label}\n\n" + "\n".join(lines) + f"\n\nTotal: {format_amount(total, base)}"

    budget_data = await budget_vs_actual(message.chat.id, start, end)
    if budget_data:
        budget_lines = []
        for bd in budget_data:
            label = bd["category"] or "Total"
            pct = bd["pct"]
            filled = min(int(pct / 100 * 10), 10)
            bar = "█" * filled + "░" * (10 - filled)
            budget_lines.append(f"  {label}: {bar} {pct:.0f}% ({format_amount(bd['remaining'], base)} left)")
        text += "\n\n💰 Budget:\n" + "\n".join(budget_lines)

    chart_path = await spending_by_category_chart(data, base)
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

    base = await get_base_currency(message.chat.id)
    lines = [f"• {row['month']}: {format_amount(row['total'], base)} ({row['count']} items)" for row in reversed(data)]

    text = "📈 Monthly spending:\n\n" + "\n".join(lines)

    chart_path = await monthly_trend_chart(list(reversed(data)), base)
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

    base = await get_base_currency(message.chat.id)
    total = sum(row["total"] for row in data)
    avg = total / 30
    text = (
        f"Daily spending (last 30 days)\n\nTotal: {format_amount(total, base)}\nDaily avg: {format_amount(avg, base)}"
    )

    budget_data = await budget_vs_actual(message.chat.id, start, today)
    total_budget = None
    if budget_data:
        for bd in budget_data:
            if bd["category"] is None:
                total_budget = bd["budget"]
                break

    chart_path = await daily_spending_chart(data, base, budget=total_budget)
    if chart_path:
        try:
            await message.answer_photo(FSInputFile(chart_path), caption=text)
        finally:
            Path(chart_path).unlink(missing_ok=True)
    else:
        await message.answer(text)


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    stats = await all_time_stats(message.chat.id)
    if not stats:
        await message.answer("No expenses recorded yet.")
        return

    base = await get_base_currency(message.chat.id)

    lines = [
        "📊 All-time Stats\n",
        f"Total expenses: {stats['count']}",
        f"Total spent: {format_amount(stats['total'], base)}",
        f"Average expense: {format_amount(stats['avg_expense'], base)}",
        f"Biggest expense: {format_amount(stats['max_expense'], base)}",
        f"First expense: {stats['first_date']}",
        f"Latest expense: {stats['last_date']}",
    ]

    if stats["top_categories"]:
        lines.append("\nTop categories:")
        for c in stats["top_categories"]:
            lines.append(f"  • {c['category'] or 'uncategorized'}: {format_amount(c['total'], base)}")

    if stats["top_stores"]:
        lines.append("\nTop stores:")
        for s in stats["top_stores"]:
            lines.append(f"  • {s['store']}: {format_amount(s['total'], base)} ({s['count']}x)")

    months = stats["monthly_comparison"]
    if len(months) == 2:
        diff = months[0]["total"] - months[1]["total"]
        pct = (diff / months[1]["total"] * 100) if months[1]["total"] else 0
        arrow = "↑" if diff > 0 else "↓"
        lines.append(f"\nMonth-over-month: {arrow} {abs(pct):.0f}% ({format_amount(abs(diff), base)})")

    await message.answer("\n".join(lines))


@router.message(Command("search"))
async def cmd_search(message: Message) -> None:
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Usage: /search coffee\n/search coffee 2025-01")
        return

    args = parts[1].strip().split()
    query = args[0]
    date_filter = args[1] if len(args) > 1 else None

    start_date = end_date = None
    if date_filter:
        try:
            from calendar import monthrange

            parts_d = date_filter.split("-")
            year, month = int(parts_d[0]), int(parts_d[1])
            start_date = date(year, month, 1)
            end_date = date(year, month, monthrange(year, month)[1])
        except (ValueError, IndexError):
            pass

    results = await search_expenses(message.chat.id, query, start_date, end_date)

    if not results:
        await message.answer(f"No expenses matching '{query}'.")
        return

    base = await get_base_currency(message.chat.id)
    lines = [f"🔍 Found {len(results)} expense(s) matching '{query}':\n"]
    for e in results[:10]:
        store = e.get("store") or ""
        cat = e.get("category") or ""
        desc = f"{store} — {cat}" if store and cat else store or cat or "—"
        note = f" — 📝 {e['note']}" if e.get("note") else ""
        lines.append(f"• {e['expense_date']}: {format_amount(e['amount_eur'], base)} ({desc}){note}")

    if len(results) > 10:
        lines.append(f"\n... and {len(results) - 10} more")

    total = sum(e["amount_eur"] for e in results)
    lines.append(f"\nTotal: {format_amount(total, base)}")

    await message.answer("\n".join(lines))
