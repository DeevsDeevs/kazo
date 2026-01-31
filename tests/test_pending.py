import time
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kazo.db.models import Expense
from kazo.handlers.pending import (
    PendingExpense,
    _cleanup_expired,
    _make_key,
    _pending,
    confirmation_keyboard,
    on_cancel,
    on_confirm,
    store_pending,
    PENDING_TTL,
)


def _make_expense(**overrides) -> Expense:
    defaults = dict(
        id=None,
        chat_id=123,
        user_id=456,
        store="TestStore",
        amount=50.0,
        original_currency="EUR",
        amount_eur=50.0,
        exchange_rate=1.0,
        category="groceries",
        items_json=None,
        source="text",
        expense_date=date(2026, 1, 31),
    )
    defaults.update(overrides)
    return Expense(**defaults)


@pytest.fixture(autouse=True)
def clear_pending():
    _pending.clear()
    yield
    _pending.clear()


def test_make_key():
    assert _make_key(123, 456) == "123:456"


def test_confirmation_keyboard():
    kb = confirmation_keyboard()
    buttons = kb.inline_keyboard[0]
    assert len(buttons) == 2
    assert buttons[0].text == "Confirm"
    assert buttons[0].callback_data == "expense:confirm"
    assert buttons[1].text == "Cancel"
    assert buttons[1].callback_data == "expense:cancel"


def test_cleanup_expired():
    _pending["old"] = PendingExpense(
        expense=_make_expense(),
        display_text="old",
        created_at=time.monotonic() - PENDING_TTL - 1,
    )
    _pending["new"] = PendingExpense(
        expense=_make_expense(),
        display_text="new",
    )
    _cleanup_expired()
    assert "old" not in _pending
    assert "new" in _pending


@pytest.mark.asyncio
async def test_store_pending():
    msg = AsyncMock()
    sent = AsyncMock()
    sent.chat.id = 123
    sent.message_id = 789
    msg.answer = AsyncMock(return_value=sent)

    expense = _make_expense()
    result = await store_pending(msg, expense, "display")

    assert result is sent
    key = _make_key(123, 789)
    assert key in _pending
    assert _pending[key].expense is expense


@pytest.mark.asyncio
async def test_on_confirm_saves():
    expense = _make_expense()
    key = _make_key(100, 200)
    _pending[key] = PendingExpense(expense=expense, display_text="test text")

    callback = AsyncMock()
    callback.message.chat.id = 100
    callback.message.message_id = 200

    with patch("kazo.handlers.pending.save_expense", new_callable=AsyncMock) as mock_save:
        await on_confirm(callback)
        mock_save.assert_awaited_once_with(expense)

    assert key not in _pending
    callback.message.edit_text.assert_awaited_once()
    callback.answer.assert_awaited_once_with("Expense saved!")


@pytest.mark.asyncio
async def test_on_confirm_expired():
    callback = AsyncMock()
    callback.message.chat.id = 100
    callback.message.message_id = 200

    await on_confirm(callback)

    callback.answer.assert_awaited_once_with("This expense has expired or was already handled.")
    callback.message.edit_reply_markup.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_cancel():
    expense = _make_expense()
    key = _make_key(100, 200)
    _pending[key] = PendingExpense(expense=expense, display_text="test text")

    callback = AsyncMock()
    callback.message.chat.id = 100
    callback.message.message_id = 200

    await on_cancel(callback)

    assert key not in _pending
    callback.message.edit_text.assert_awaited_once_with("Expense cancelled.")
    callback.answer.assert_awaited_once_with("Cancelled.")
