import csv
import io
import logging
from calendar import monthrange
from datetime import date
from pathlib import Path

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, FSInputFile, Message

from kazo.config import settings
from kazo.currency import get_base_currency
from kazo.services.expense_service import get_expenses

logger = logging.getLogger(__name__)
router = Router()


def _parse_month(text: str | None) -> tuple[date, date] | None:
    if not text:
        return None
    text = text.strip()
    try:
        parts = text.split("-")
        year = int(parts[0])
        month = int(parts[1])
        if not (1 <= month <= 12):
            return None
        start = date(year, month, 1)
        end = date(year, month, monthrange(year, month)[1])
        return start, end
    except (ValueError, IndexError):
        return None


@router.message(Command("export"))
async def cmd_export(message: Message):
    parts = message.text.split(maxsplit=1) if message.text else []
    arg = parts[1] if len(parts) > 1 else None

    if arg:
        result = _parse_month(arg)
        if not result:
            await message.answer("Invalid month format. Use: /export 2025-01")
            return
        start, end = result
    else:
        today = date.today()
        start = today.replace(day=1)
        end = date(today.year, today.month, monthrange(today.year, today.month)[1])

    expenses = await get_expenses(message.chat.id, start_date=start, end_date=end)

    if not expenses:
        await message.answer(f"No expenses for {start.strftime('%B %Y')}.")
        return

    base = await get_base_currency(message.chat.id)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Store", "Category", "Amount", "Currency", f"Amount {base}", "Source", "Note"])
    for e in expenses:
        writer.writerow(
            [
                e.get("expense_date", ""),
                e.get("store", ""),
                e.get("category", ""),
                e.get("amount", ""),
                e.get("original_currency", ""),
                e.get("amount_eur", ""),
                e.get("source", ""),
                e.get("note", ""),
            ]
        )

    filename = f"expenses_{start.strftime('%Y_%m')}.csv"
    file_bytes = buf.getvalue().encode("utf-8")
    doc = BufferedInputFile(file_bytes, filename=filename)
    await message.answer_document(doc, caption=f"Expenses for {start.strftime('%B %Y')} ({len(expenses)} records)")


@router.message(Command("backup"))
async def cmd_backup(message: Message):
    db_path = Path(settings.db_path)
    if not db_path.exists():
        await message.answer("No database file found.")
        return

    doc = FSInputFile(db_path, filename=f"kazo_backup_{date.today().isoformat()}.db")
    size_mb = db_path.stat().st_size / (1024 * 1024)
    await message.answer_document(doc, caption=f"Kazo database backup ({size_mb:.1f} MB)")
