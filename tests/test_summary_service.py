from datetime import date

from kazo.db.models import Expense
from kazo.services.expense_service import save_expense
from kazo.services.summary_service import daily_spending, spending_by_category


def _exp(**kw) -> Expense:
    defaults = dict(
        id=None,
        chat_id=1,
        user_id=1,
        store=None,
        amount=10.0,
        original_currency="EUR",
        amount_base=10.0,
        exchange_rate=1.0,
        category="groceries",
        items_json=None,
        source="text",
        expense_date=date(2025, 3, 1),
    )
    defaults.update(kw)
    return Expense(**defaults)


async def test_spending_by_category():
    await save_expense(_exp(category="groceries", amount_base=30.0))
    await save_expense(_exp(category="groceries", amount_base=20.0))
    await save_expense(_exp(category="dining", amount_base=15.0))

    result = await spending_by_category(1, date(2025, 3, 1), date(2025, 3, 31))
    assert len(result) == 2
    assert result[0]["category"] == "groceries"
    assert result[0]["total"] == 50.0


async def test_daily_spending():
    await save_expense(_exp(expense_date=date(2025, 3, 1), amount_base=10.0))
    await save_expense(_exp(expense_date=date(2025, 3, 1), amount_base=5.0))
    await save_expense(_exp(expense_date=date(2025, 3, 2), amount_base=20.0))

    result = await daily_spending(1, date(2025, 3, 1), date(2025, 3, 2))
    assert len(result) == 2
    assert result[0]["total"] == 15.0
    assert result[1]["total"] == 20.0
