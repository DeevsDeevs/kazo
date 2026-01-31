import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from kazo.db.models import Expense
from kazo.services.expense_service import save_expense

logger = logging.getLogger(__name__)
router = Router()

PENDING_TTL = 300  # 5 minutes

@dataclass(slots=True)
class PendingExpense:
    expense: Expense
    display_text: str
    created_at: float = field(default_factory=time.monotonic)


_pending: dict[str, PendingExpense] = {}


def _make_key(chat_id: int, message_id: int) -> str:
    return f"{chat_id}:{message_id}"


def _cleanup_expired():
    now = time.monotonic()
    expired = [k for k, v in _pending.items() if now - v.created_at > PENDING_TTL]
    for k in expired:
        del _pending[k]


def confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Confirm", callback_data="expense:confirm"),
        InlineKeyboardButton(text="Cancel", callback_data="expense:cancel"),
    ]])


async def store_pending(message: Message, expense: Expense, display_text: str) -> Message:
    _cleanup_expired()
    sent = await message.answer(display_text, reply_markup=confirmation_keyboard())
    key = _make_key(sent.chat.id, sent.message_id)
    _pending[key] = PendingExpense(expense=expense, display_text=display_text)
    return sent


@router.callback_query(lambda c: c.data == "expense:confirm")
async def on_confirm(callback: CallbackQuery):
    key = _make_key(callback.message.chat.id, callback.message.message_id)
    pending = _pending.pop(key, None)

    if not pending:
        await callback.answer("This expense has expired or was already handled.")
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    await save_expense(pending.expense)
    await callback.message.edit_text(pending.display_text + "\n\nSaved.")
    await callback.answer("Expense saved!")


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
