import json
import logging
import time
from dataclasses import dataclass, field

from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from kazo.currency import format_amount, get_base_currency
from kazo.db.models import Expense
from kazo.services.expense_service import detect_recurring, link_bot_message, save_expense

logger = logging.getLogger(__name__)
router = Router()

PENDING_TTL = 300  # 5 minutes


@dataclass(slots=True)
class PendingExpense:
    expense: Expense
    display_text: str
    items: list[dict] | None = None
    created_at: float = field(default_factory=time.monotonic)


_pending: dict[str, PendingExpense] = {}


def _make_key(chat_id: int, message_id: int) -> str:
    return f"{chat_id}:{message_id}"


def _cleanup_expired():
    now = time.monotonic()
    expired = [k for k, v in _pending.items() if now - v.created_at > PENDING_TTL]
    for k in expired:
        del _pending[k]


def confirmation_keyboard(has_items: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text="Confirm", callback_data="expense:confirm"),
    ]
    if has_items:
        buttons.append(InlineKeyboardButton(text="Edit Items", callback_data="expense:edit_items"))
    buttons.append(InlineKeyboardButton(text="Cancel", callback_data="expense:cancel"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def _items_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for i, item in enumerate(items):
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"Remove: {item['name']} ({item['price']:.2f})",
                    callback_data=f"expense:remove:{i}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(text="Done → Save", callback_data="expense:confirm"),
            InlineKeyboardButton(text="Cancel", callback_data="expense:cancel"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _build_receipt_display(pending: PendingExpense) -> str:
    expense = pending.expense
    currency = expense.original_currency
    items = pending.items or []

    total = sum(i["price"] for i in items) if items else expense.amount

    amount_eur = total * (expense.amount_eur / expense.amount) if expense.amount else total

    base = await get_base_currency(expense.chat_id)
    currency_note = f" ({total:.2f} {currency})" if currency != base else ""
    items_text = ""
    if items:
        items_lines = [f"  • {i['name']}: {i['price']:.2f}" for i in items[:10]]
        items_text = "\n" + "\n".join(items_lines)

    return (
        f"🧾 Receipt processed\n"
        f"💰 {format_amount(amount_eur, base)}{currency_note}\n"
        f"🏷 {expense.category}\n"
        f"📅 {expense.expense_date}" + (f"\n🏪 {expense.store}" if expense.store else "") + items_text
    )


async def store_pending(message: Message, expense: Expense, display_text: str) -> Message:
    _cleanup_expired()
    items = json.loads(expense.items_json) if expense.items_json else None
    has_items = bool(items)
    sent = await message.answer(display_text, reply_markup=confirmation_keyboard(has_items))
    key = _make_key(sent.chat.id, sent.message_id)
    _pending[key] = PendingExpense(expense=expense, display_text=display_text, items=items)
    return sent


@router.callback_query(lambda c: c.data == "expense:confirm")
async def on_confirm(callback: CallbackQuery):
    key = _make_key(callback.message.chat.id, callback.message.message_id)
    pending = _pending.pop(key, None)

    if not pending:
        await callback.answer("This expense has expired or was already handled.")
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    expense = pending.expense
    if pending.items is not None:
        new_total = sum(i["price"] for i in pending.items)
        if new_total != expense.amount:
            expense.amount = new_total
            expense.amount_eur = new_total / expense.exchange_rate if expense.exchange_rate else new_total
            expense.items_json = json.dumps(pending.items)

    display = await _build_receipt_display(pending) if pending.items is not None else pending.display_text
    expense_id = await save_expense(expense)
    await link_bot_message(callback.message.chat.id, callback.message.message_id, expense_id)

    suffix = "\n\nSaved ✓ (reply to edit)"
    if expense.store and await detect_recurring(expense.chat_id, expense.store, expense.amount_eur):
        suffix += (
            f"\n\n💡 You've paid {expense.store} similar amounts multiple times. "
            f"Consider adding as subscription: /addsub {expense.store} {expense.amount_eur:.2f} "
            f"{expense.original_currency} monthly"
        )

    await callback.message.edit_text(display + suffix)
    await callback.answer("Expense saved!")


@router.callback_query(lambda c: c.data == "expense:edit_items")
async def on_edit_items(callback: CallbackQuery):
    key = _make_key(callback.message.chat.id, callback.message.message_id)
    pending = _pending.get(key)

    if not pending or not pending.items:
        await callback.answer("No items to edit.")
        return

    display = await _build_receipt_display(pending)
    await callback.message.edit_text(display, reply_markup=_items_keyboard(pending.items))
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("expense:remove:"))
async def on_remove_item(callback: CallbackQuery):
    key = _make_key(callback.message.chat.id, callback.message.message_id)
    pending = _pending.get(key)

    if not pending or not pending.items:
        await callback.answer("This expense has expired or was already handled.")
        return

    try:
        idx = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Invalid item.")
        return

    if idx < 0 or idx >= len(pending.items):
        await callback.answer("Item not found.")
        return

    removed = pending.items.pop(idx)
    await callback.answer(f"Removed {removed['name']}")

    if not pending.items:
        _pending.pop(key, None)
        await callback.message.edit_text("All items removed — expense cancelled.")
        return

    display = await _build_receipt_display(pending)
    await callback.message.edit_text(display, reply_markup=_items_keyboard(pending.items))


@router.callback_query(lambda c: c.data == "expense:cancel")
async def on_cancel(callback: CallbackQuery):
    key = _make_key(callback.message.chat.id, callback.message.message_id)
    pending = _pending.pop(key, None)

    if not pending:
        await callback.answer("This expense has expired or was already handled.")
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    await callback.message.edit_text("Expense cancelled.")
    await callback.answer("Cancelled.")
