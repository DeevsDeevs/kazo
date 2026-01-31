import csv
import io
from datetime import date

from kazo.db.database import get_db
from kazo.handlers.export import _parse_month
from kazo.services.expense_service import get_expenses

CHAT = 100


async def _add_expense(chat_id, amount, category, expense_date, store="TestStore"):
    db = await get_db()
    await db.execute(
        """INSERT INTO expenses (chat_id, user_id, store, amount, original_currency,
        amount_eur, exchange_rate, category, source, expense_date)
        VALUES (?, 1, ?, ?, 'EUR', ?, 1.0, ?, 'text', ?)""",
        (chat_id, store, amount, amount, category, expense_date),
    )
    await db.commit()


def test_parse_month_valid():
    result = _parse_month("2025-01")
    assert result == (date(2025, 1, 1), date(2025, 1, 31))


def test_parse_month_feb_leap():
    result = _parse_month("2024-02")
    assert result == (date(2024, 2, 1), date(2024, 2, 29))


def test_parse_month_invalid():
    assert _parse_month("abc") is None
    assert _parse_month("2025-13") is None
    assert _parse_month("2025-00") is None
    assert _parse_month(None) is None
    assert _parse_month("") is None


async def test_export_csv_content():
    await _add_expense(CHAT, 50.0, "groceries", "2025-01-15", "Lidl")
    await _add_expense(CHAT, 30.0, "dining", "2025-01-20", "Restaurant")

    expenses = await get_expenses(CHAT, date(2025, 1, 1), date(2025, 1, 31))
    assert len(expenses) == 2

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Store", "Category", "Amount", "Currency", "Amount EUR", "Source"])
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
            ]
        )

    buf.seek(0)
    reader = csv.reader(buf)
    rows = list(reader)
    assert rows[0] == ["Date", "Store", "Category", "Amount", "Currency", "Amount EUR", "Source"]
    assert len(rows) == 3
    assert rows[1][1] == "Restaurant"  # most recent first
    assert rows[2][1] == "Lidl"


async def test_export_no_expenses():
    expenses = await get_expenses(CHAT, date(2025, 6, 1), date(2025, 6, 30))
    assert expenses == []


async def test_export_filters_by_chat():
    await _add_expense(CHAT, 50.0, "groceries", "2025-01-15")
    await _add_expense(999, 30.0, "dining", "2025-01-15")

    expenses = await get_expenses(CHAT, date(2025, 1, 1), date(2025, 1, 31))
    assert len(expenses) == 1
