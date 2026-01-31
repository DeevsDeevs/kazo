import json
import logging
import re
from datetime import date, datetime
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from kazo.categories import get_categories, get_categories_str
from kazo.claude.client import ask_claude, ask_claude_structured
from kazo.currency import format_amount, get_base_currency
from kazo.db.models import Expense
from kazo.handlers.pending import store_pending
from kazo.services.currency_service import convert_to_base
from kazo.services.expense_service import (
    delete_last_expense,
    get_expense_by_bot_message,
    get_expense_by_id,
    get_expenses,
    get_last_expense,
    link_bot_message,
    update_expense,
)

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
        "note": {"type": ["string", "null"]},
        "expense_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
        "items": {
            "type": ["array", "null"],
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "price": {"type": ["number", "null"]},
                    "quantity": {"type": "number", "default": 1},
                },
                "required": ["name"],
            },
        },
    },
    "required": ["amount", "currency", "category", "description", "expense_date"],
    "additionalProperties": False,
}


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Welcome to Kazo — your family expense tracker!\n\n"
        "Just chat naturally to log expenses:\n"
        '  "spent 50 on groceries"\n'
        '  "coffee 4.50 at Starbucks"\n'
        '  "lunch yesterday 12 euros"\n\n'
        "Send a receipt photo or PDF and I'll extract it automatically.\n"
        "Send a product photo and I'll identify items for you.\n\n"
        "Reply to any confirmed expense to edit it.\n"
        'You can also ask questions: "how much on dining this month?"\n\n'
        "Type /help for all commands."
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Tracking expenses:\n"
        '  Send text with amount: "spent 50 on groceries"\n'
        "  Send receipt photo/PDF\n"
        "  Send product photo\n\n"
        "Editing:\n"
        "  Reply to expense → type correction\n"
        "  /edit — edit last expense\n"
        "  /edit <id> — edit specific expense\n"
        "  /note <text> — add note to last expense\n"
        "  /undo — remove last expense\n\n"
        "Reports:\n"
        "  /summary — this month's spending + chart\n"
        "  /monthly — month-over-month comparison\n"
        "  /daily — daily spending chart\n"
        "  /stats — all-time statistics\n"
        "  /budget — budget status\n"
        "  /search <keyword> — find expenses\n"
        "  /export — download CSV\n"
        "  /backup — download database\n\n"
        "Items & prices:\n"
        "  /price <item> — price history\n"
        "  /items — recent items\n"
        "  /compare <item> — compare across stores\n\n"
        "Setup:\n"
        "  /subs — subscriptions\n"
        "  /addsub / /removesub — manage subscriptions\n"
        "  /categories — view categories\n"
        "  /addcategory / /removecategory\n"
        "  /setbudget <amount> — monthly budget\n"
        "  /setcurrency <code> — change base currency\n"
        "  /rate <currency> — exchange rates\n"
        "  /settings — view current config\n\n"
        'You can also ask naturally: "how much on groceries?"'
    )


@router.message(Command("undo"))
async def cmd_undo(message: Message):
    deleted = await delete_last_expense(message.chat.id)
    if not deleted:
        await message.answer("No expenses to undo.")
        return
    base = await get_base_currency(message.chat.id)
    await message.answer(
        f"Removed: {format_amount(deleted['amount_base'], base)} — {deleted['category']} ({deleted['expense_date']})"
    )


@router.message(Command("edit"))
async def cmd_edit(message: Message):
    args = message.text.strip().split(maxsplit=1) if message.text else []
    edit_arg = args[1] if len(args) > 1 else None

    if edit_arg and edit_arg.isdigit():
        expense = await get_expense_by_id(int(edit_arg))
        if not expense or expense["chat_id"] != message.chat.id:
            await message.answer("Expense not found.")
            return
    else:
        expense = await get_last_expense(message.chat.id)
        if not expense:
            await message.answer("No expenses found.")
            return

    base = await get_base_currency(message.chat.id)
    currency_note = (
        f" ({expense['amount']} {expense['original_currency']})" if expense["original_currency"] != base else ""
    )
    text = (
        f"Expense #{expense['id']}:\n"
        f"💰 {format_amount(expense['amount_base'], base)}{currency_note}\n"
        f"🏷 {expense['category']}\n"
        f"📅 {expense['expense_date']}"
        + (f"\n🏪 {expense['store']}" if expense.get("store") else "")
        + (f"\n📝 {expense['note']}" if expense.get("note") else "")
        + "\n\nReply to this message with your correction."
    )

    sent = await message.answer(text)
    await link_bot_message(message.chat.id, sent.message_id, expense["id"])


@router.message(Command("note"))
async def cmd_note(message: Message):
    args = message.text.strip().split(maxsplit=2) if message.text else []
    # /note <id> <text> or /note <text> (applies to last expense)
    if len(args) < 2:
        await message.answer("Usage: /note <text> or /note <id> <text>")
        return

    if len(args) >= 3 and args[1].isdigit():
        expense_id = int(args[1])
        note_text = args[2]
        expense = await get_expense_by_id(expense_id)
        if not expense or expense["chat_id"] != message.chat.id:
            await message.answer("Expense not found.")
            return
    else:
        note_text = " ".join(args[1:])
        expense = await get_last_expense(message.chat.id)
        if not expense:
            await message.answer("No expenses found.")
            return
        expense_id = expense["id"]

    await update_expense(expense_id, note=note_text)
    await message.answer(f"Note added to expense #{expense_id}: {note_text}")


INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": [
                "expense",
                "undo",
                "edit",
                "summary",
                "query",
                "categories",
                "subscriptions",
                "rate",
                "search",
                "price",
                "items",
                "help",
                "chat",
            ],
        },
        "args": {
            "type": "string",
            "description": "Extracted argument if any (e.g. item name for price, category name for categories)",
        },
    },
    "required": ["intent"],
    "additionalProperties": False,
}


async def _classify_intent(text: str) -> dict:
    system_prompt = (PROMPTS_DIR / "classify_intent.txt").read_text()
    return await ask_claude_structured(
        prompt=text,
        json_schema=INTENT_SCHEMA,
        system_prompt=system_prompt,
    )


async def _handle_query(message: Message):
    from kazo.services.summary_service import spending_by_category

    today = date.today()
    start = today.replace(day=1)
    expenses = await get_expenses(message.chat.id, start_date=start, end_date=today)
    base = await get_base_currency(message.chat.id)

    if not expenses:
        await message.answer("No expenses this month to analyze.")
        return

    summary_lines = []
    for e in expenses[:50]:
        line = f"{e['expense_date']} | {e.get('store', '?')} | {e['category']} | {e['amount_base']:.2f} {base}"
        if e.get("note"):
            line += f" | {e['note']}"
        summary_lines.append(line)

    data_text = "\n".join(summary_lines)
    by_cat = await spending_by_category(message.chat.id, start, today)
    cat_text = ", ".join(f"{c['category']}: {c['total']:.2f}" for c in by_cat) if by_cat else "none"

    answer = await ask_claude(
        prompt=(
            f"User question: {message.text}\n\n"
            f"Expense data (this month, {base}):\n{data_text}\n\n"
            f"By category: {cat_text}"
        ),
        system_prompt=(
            f"You are Kazo, a family expense tracker. Answer the user's question based on the expense data provided. "
            f"Be concise (2-4 sentences). Use {base} for amounts. If the data doesn't contain enough info, say so."
        ),
        chat_id=message.chat.id,
    )
    await message.answer(answer)


async def _handle_conversational_intent(message: Message, intent: str, args: str | None):
    if intent == "undo":
        await cmd_undo(message)
    elif intent == "edit":
        await cmd_edit(message)
    elif intent == "summary":
        from kazo.handlers.summary import cmd_summary

        await cmd_summary(message)
    elif intent == "query":
        await _handle_query(message)
    elif intent == "categories":
        from kazo.handlers.categories import cmd_categories

        await cmd_categories(message)
    elif intent == "subscriptions":
        from kazo.handlers.subscriptions import cmd_subs

        await cmd_subs(message)
    elif intent == "rate":
        from kazo.handlers.currencies import cmd_rate

        await cmd_rate(message)
    elif intent == "price":
        if args:
            from kazo.handlers.items import cmd_price

            message.text = f"/price {args}"
            await cmd_price(message)
        else:
            await message.answer("What item do you want to check? Try: /price tomatoes")
    elif intent == "items":
        from kazo.handlers.items import cmd_items

        message.text = f"/items {args or ''}"
        await cmd_items(message)
    elif intent == "search":
        if args:
            await message.answer(f"Try: /search {args}\n(Search coming soon!)")
        else:
            await message.answer("What would you like to search for?")
    elif intent == "help":
        await cmd_start(message)
    elif intent == "chat":
        await message.answer(
            await ask_claude(
                prompt=message.text,
                system_prompt=(
                    "You are Kazo, a family expense tracker bot. Respond briefly and friendly. "
                    "Keep it to 1-2 sentences. "
                    "If they seem to want to log an expense, remind them to include an amount."
                ),
                chat_id=message.chat.id,
            )
        )


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_expense(message: Message):
    if not message.from_user:
        return

    if not message.text:
        return

    if not _HAS_NUMBER.search(message.text):
        try:
            result = await _classify_intent(message.text)
            intent = result.get("intent", "chat")
            args = result.get("args")
            await _handle_conversational_intent(message, intent, args)
        except Exception:
            logger.exception("Intent classification failed", extra={"chat_id": message.chat.id})
        return

    base = await get_base_currency(message.chat.id)
    categories_str = await get_categories_str(message.chat.id)
    system_prompt = (
        (PROMPTS_DIR / "parse_expense.txt")
        .read_text()
        .format(
            categories=categories_str,
            today=date.today().isoformat(),
            base_currency=base,
        )
    )

    try:
        parsed = await ask_claude_structured(
            prompt=message.text,
            json_schema=EXPENSE_SCHEMA,
            system_prompt=system_prompt,
            chat_id=message.chat.id,
        )
    except Exception:
        logger.exception("Failed to parse expense", extra={"chat_id": message.chat.id})
        await message.answer('Sorry, I couldn\'t understand that. Try something like "spent 50 on groceries".')
        return

    try:
        amount = parsed["amount"]
        currency = parsed["currency"].upper()
        category = parsed["category"].lower()
    except (KeyError, AttributeError):
        logger.exception("Malformed Claude response: %s", parsed, extra={"chat_id": message.chat.id})
        await message.answer("Sorry, I couldn't parse that properly. Please try again.")
        return

    if amount <= 0:
        await message.answer("Couldn't determine a valid amount. Please try again.")
        return

    store = parsed.get("store")
    note = parsed.get("note")
    items = parsed.get("items")
    items_json = json.dumps(items) if items else None
    expense_date = parsed.get("expense_date", date.today().isoformat())
    try:
        datetime.strptime(expense_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        logger.warning("Invalid date from Claude: %s, using today", expense_date, extra={"chat_id": message.chat.id})
        expense_date = date.today().isoformat()

    amount_base, rate = await convert_to_base(amount, currency, message.chat.id)

    expense = Expense(
        id=None,
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        store=store,
        amount=amount,
        original_currency=currency,
        amount_base=amount_base,
        exchange_rate=rate,
        category=category,
        items_json=items_json,
        source="text",
        expense_date=expense_date,
        note=note,
    )

    all_categories = await get_categories(message.chat.id)
    is_new_category = category not in all_categories
    cat_note = " (new category)" if is_new_category else ""
    currency_note = f" ({amount} {currency})" if currency != base else ""

    items_text = ""
    if items:
        item_lines = []
        for item in items:
            name = item.get("name", "?")
            price = item.get("price")
            qty = item.get("quantity", 1)
            if price is not None:
                line = f"  {name}: {price:.2f} {currency}" + (f" x{qty:.0f}" if qty != 1 else "")
            else:
                line = f"  {name}" + (f" x{qty:.0f}" if qty != 1 else "")
            item_lines.append(line)
        items_text = "\n🛒 Items:\n" + "\n".join(item_lines)

    display_text = (
        f"✅ {parsed.get('description', 'Expense recorded')}\n"
        f"💰 {format_amount(amount_base, base)}{currency_note}\n"
        f"🏷 {category}{cat_note}\n"
        f"📅 {expense_date}" + (f"\n🏪 {store}" if store else "") + (f"\n📝 {note}" if note else "") + items_text
    )

    await store_pending(message, expense, display_text)


EDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "amount": {"type": "number", "exclusiveMinimum": 0},
        "currency": {"type": "string", "pattern": "^[A-Z]{3}$"},
        "category": {"type": "string", "minLength": 1},
        "store": {"type": ["string", "null"]},
        "note": {"type": ["string", "null"]},
        "expense_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
    },
    "additionalProperties": False,
}


@router.message(F.reply_to_message & F.text & ~F.text.startswith("/"))
async def handle_edit_reply(message: Message):
    reply = message.reply_to_message
    if not reply or not reply.from_user or not reply.from_user.is_bot:
        return

    expense = await get_expense_by_bot_message(message.chat.id, reply.message_id)
    if not expense:
        return

    base = await get_base_currency(message.chat.id)
    categories_str = await get_categories_str(message.chat.id)
    edit_prompt = (
        (PROMPTS_DIR / "edit_expense.txt")
        .read_text()
        .format(
            amount=expense["amount"],
            currency=expense["original_currency"],
            amount_base=expense["amount_base"],
            category=expense["category"],
            store=expense["store"] or "none",
            expense_date=expense["expense_date"],
            correction=message.text,
            categories=categories_str,
            today=date.today().isoformat(),
            base_currency=base,
        )
    )

    try:
        changes = await ask_claude_structured(
            prompt=message.text,
            json_schema=EDIT_SCHEMA,
            system_prompt=edit_prompt,
            chat_id=message.chat.id,
        )
    except Exception:
        logger.exception("Failed to parse edit", extra={"chat_id": message.chat.id})
        await message.answer("Sorry, I couldn't understand that edit.")
        return

    if not changes:
        await message.answer("No changes detected.")
        return

    if "amount" in changes or "currency" in changes:
        amt = changes.get("amount", expense["amount"])
        cur = changes.get("currency", expense["original_currency"])
        amount_base, rate = await convert_to_base(amt, cur, message.chat.id)
        changes["amount"] = amt
        changes["original_currency"] = cur
        changes["amount_base"] = amount_base
        changes["exchange_rate"] = rate
        if "currency" in changes:
            del changes["currency"]

    if "category" in changes:
        changes["category"] = changes["category"].lower()

    updated = await update_expense(expense["id"], **changes)
    if not updated:
        await message.answer("Could not update the expense.")
        return

    parts = []
    for k, v in changes.items():
        if k in ("exchange_rate",):
            continue
        label = k.replace("_", " ").title()
        if k == "amount_base":
            parts.append(f"Amount: {format_amount(v, base)}")
        elif k == "original_currency":
            continue
        elif k == "amount":
            cur = changes.get("original_currency", expense["original_currency"])
            parts.append(f"Amount: {v} {cur}")
        else:
            parts.append(f"{label}: {v}")

    await message.answer(f"Updated: {', '.join(parts)}")
