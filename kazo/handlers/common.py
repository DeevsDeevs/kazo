import logging
import re
from datetime import date, datetime
from pathlib import Path

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from kazo.categories import get_categories, get_categories_str
from kazo.claude.client import ask_claude_structured
from kazo.db.models import Expense
from kazo.services.currency_service import convert_to_eur
from kazo.services.expense_service import save_expense

logger = logging.getLogger(__name__)
router = Router()

_HAS_NUMBER = re.compile(r"\d")

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

EXPENSE_SCHEMA = {
    "type": "object",
    "properties": {
        "amount": {"type": "number", "exclusiveMinimum": 0},
        "currency": {"type": "string", "pattern": "^[A-Z]{3}$"},
        "category": {"type": "string", "minLength": 1},
        "store": {"type": ["string", "null"]},
        "description": {"type": "string", "minLength": 1},
        "expense_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
    },
    "required": ["amount", "currency", "category", "description", "expense_date"],
    "additionalProperties": False,
}


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Welcome to Kazo! I track your family expenses.\n\n"
        "Just send me a message like \"spent 50 on groceries\" "
        "or send a receipt photo.\n\n"
        "Commands:\n"
        "/help — show this message\n"
        "/summary — this month's spending\n"
        "/monthly — month-over-month comparison\n"
        "/subs — list subscriptions\n"
        "/addsub — add subscription\n"
        "/removesub — remove subscription\n"
        "/categories — list all categories\n"
        "/addcategory — add custom category\n"
        "/removecategory — remove custom category\n"
        "/rate — check exchange rates"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await cmd_start(message)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_expense(message: Message):
    if not message.from_user:
        return

    if not message.text or not _HAS_NUMBER.search(message.text):
        logger.debug("Ignoring non-expense message: %s", message.text)
        return

    categories_str = await get_categories_str(message.chat.id)
    system_prompt = (PROMPTS_DIR / "parse_expense.txt").read_text().format(
        categories=categories_str,
        today=date.today().isoformat(),
    )

    try:
        parsed = await ask_claude_structured(
            prompt=message.text,
            json_schema=EXPENSE_SCHEMA,
            system_prompt=system_prompt,
        )
    except Exception:
        logger.exception("Failed to parse expense")
        await message.answer("Sorry, I couldn't understand that. Try something like \"spent 50 on groceries\".")
        return

    try:
        amount = parsed["amount"]
        currency = parsed["currency"].upper()
        category = parsed["category"].lower()
    except (KeyError, AttributeError):
        logger.exception("Malformed Claude response: %s", parsed)
        await message.answer("Sorry, I couldn't parse that properly. Please try again.")
        return

    if amount <= 0:
        await message.answer("Couldn't determine a valid amount. Please try again.")
        return

    store = parsed.get("store")
    expense_date = parsed.get("expense_date", date.today().isoformat())
    try:
        datetime.strptime(expense_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        logger.warning("Invalid date from Claude: %s, using today", expense_date)
        expense_date = date.today().isoformat()

    amount_eur, rate = await convert_to_eur(amount, currency)

    expense = Expense(
        id=None,
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        store=store,
        amount=amount,
        original_currency=currency,
        amount_eur=amount_eur,
        exchange_rate=rate,
        category=category,
        items_json=None,
        source="text",
        expense_date=expense_date,
    )

    await save_expense(expense)

    all_categories = await get_categories(message.chat.id)
    is_new_category = category not in all_categories
    cat_note = " (new category)" if is_new_category else ""
    currency_note = f" ({amount} {currency})" if currency != "EUR" else ""

    await message.answer(
        f"✅ {parsed.get('description', 'Expense recorded')}\n"
        f"💰 €{amount_eur:.2f}{currency_note}\n"
        f"🏷 {category}{cat_note}\n"
        f"📅 {expense_date}"
        + (f"\n🏪 {store}" if store else "")
    )
