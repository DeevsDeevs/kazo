import json
import time
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from kazo.db.models import Expense
from kazo.handlers.pending import (
    PENDING_TTL,
    PendingExpense,
    _build_receipt_display,
    _cleanup_expired,
    _items_keyboard,
    _make_key,
    _pending,
    confirmation_keyboard,
    on_cancel,
    on_confirm,
    on_edit_items,
    on_remove_item,
    store_pending,
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


def test_confirmation_keyboard_no_items():
    kb = confirmation_keyboard()
    buttons = kb.inline_keyboard[0]
    assert len(buttons) == 2
    assert buttons[0].text == "Confirm"
    assert buttons[1].text == "Cancel"


def test_confirmation_keyboard_with_items():
    kb = confirmation_keyboard(has_items=True)
    buttons = kb.inline_keyboard[0]
    assert len(buttons) == 3
    assert buttons[0].text == "Confirm"
    assert buttons[1].text == "Edit Items"
    assert buttons[1].callback_data == "expense:edit_items"
    assert buttons[2].text == "Cancel"


def test_items_keyboard():
    items = [{"name": "Milk", "price": 2.50}, {"name": "Bread", "price": 1.80}]
    kb = _items_keyboard(items)
    assert len(kb.inline_keyboard) == 3  # 2 remove + 1 action row
    assert "Milk" in kb.inline_keyboard[0][0].text
    assert kb.inline_keyboard[0][0].callback_data == "expense:remove:0"
    assert kb.inline_keyboard[1][0].callback_data == "expense:remove:1"
    assert kb.inline_keyboard[2][0].text == "Done → Save"
    assert kb.inline_keyboard[2][1].text == "Cancel"


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
async def test_store_pending_no_items():
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
    assert _pending[key].items is None


@pytest.mark.asyncio
async def test_store_pending_with_items():
    msg = AsyncMock()
    sent = AsyncMock()
    sent.chat.id = 123
    sent.message_id = 789
    msg.answer = AsyncMock(return_value=sent)

    items = [{"name": "Milk", "price": 2.50}]
    expense = _make_expense(items_json=json.dumps(items))
    await store_pending(msg, expense, "display")

    key = _make_key(123, 789)
    assert _pending[key].items == items
    # Should have Edit Items button
    call_args = msg.answer.call_args
    kb = call_args.kwargs.get("reply_markup") or call_args[1].get("reply_markup")
    buttons = kb.inline_keyboard[0]
    assert any(b.text == "Edit Items" for b in buttons)


@pytest.mark.asyncio
async def test_on_confirm_saves():
    expense = _make_expense()
    key = _make_key(100, 200)
    _pending[key] = PendingExpense(expense=expense, display_text="test text")

    callback = AsyncMock()
    callback.message.chat.id = 100
    callback.message.message_id = 200

    with (
        patch("kazo.handlers.pending.save_expense", new_callable=AsyncMock, return_value=42) as mock_save,
        patch("kazo.handlers.pending.link_bot_message", new_callable=AsyncMock) as mock_link,
    ):
        await on_confirm(callback)
        mock_save.assert_awaited_once_with(expense)
        mock_link.assert_awaited_once_with(100, 200, 42)

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
async def test_on_confirm_with_edited_items():
    """Confirm after removing items recalculates total."""
    items = [{"name": "Milk", "price": 3.00}, {"name": "Bread", "price": 2.00}]
    expense = _make_expense(amount=5.0, amount_eur=5.0, items_json=json.dumps(items))
    key = _make_key(100, 200)
    # Simulate having removed Bread — only Milk remains
    _pending[key] = PendingExpense(
        expense=expense,
        display_text="test",
        items=[{"name": "Milk", "price": 3.00}],
    )

    callback = AsyncMock()
    callback.message.chat.id = 100
    callback.message.message_id = 200

    with (
        patch("kazo.handlers.pending.save_expense", new_callable=AsyncMock, return_value=42) as mock_save,
        patch("kazo.handlers.pending.link_bot_message", new_callable=AsyncMock),
    ):
        await on_confirm(callback)
        saved = mock_save.call_args[0][0]
        assert saved.amount == 3.0
        assert saved.amount_eur == 3.0


@pytest.mark.asyncio
async def test_on_edit_items():
    items = [{"name": "Milk", "price": 2.50}]
    expense = _make_expense(items_json=json.dumps(items))
    key = _make_key(100, 200)
    _pending[key] = PendingExpense(expense=expense, display_text="test", items=items)

    callback = AsyncMock()
    callback.message.chat.id = 100
    callback.message.message_id = 200
    callback.data = "expense:edit_items"

    await on_edit_items(callback)

    callback.message.edit_text.assert_awaited_once()
    call_args = callback.message.edit_text.call_args
    kb = (
        call_args.kwargs.get("reply_markup") or call_args[1].get("reply_markup")
        if len(call_args) > 1
        else call_args.kwargs.get("reply_markup")
    )
    assert kb is not None


@pytest.mark.asyncio
async def test_on_edit_items_no_items():
    callback = AsyncMock()
    callback.message.chat.id = 100
    callback.message.message_id = 200
    callback.data = "expense:edit_items"

    await on_edit_items(callback)
    callback.answer.assert_awaited_once_with("No items to edit.")


@pytest.mark.asyncio
async def test_on_remove_item():
    items = [{"name": "Milk", "price": 2.50}, {"name": "Bread", "price": 1.80}]
    expense = _make_expense(amount=4.30, amount_eur=4.30, items_json=json.dumps(items))
    key = _make_key(100, 200)
    _pending[key] = PendingExpense(expense=expense, display_text="test", items=list(items))

    callback = AsyncMock()
    callback.message.chat.id = 100
    callback.message.message_id = 200
    callback.data = "expense:remove:0"

    await on_remove_item(callback)

    assert len(_pending[key].items) == 1
    assert _pending[key].items[0]["name"] == "Bread"
    callback.answer.assert_awaited_once_with("Removed Milk")


@pytest.mark.asyncio
async def test_on_remove_last_item_cancels():
    items = [{"name": "Milk", "price": 2.50}]
    expense = _make_expense(items_json=json.dumps(items))
    key = _make_key(100, 200)
    _pending[key] = PendingExpense(expense=expense, display_text="test", items=list(items))

    callback = AsyncMock()
    callback.message.chat.id = 100
    callback.message.message_id = 200
    callback.data = "expense:remove:0"

    await on_remove_item(callback)

    assert key not in _pending
    callback.message.edit_text.assert_awaited_once_with("All items removed — expense cancelled.")


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


@pytest.mark.asyncio
async def test_build_receipt_display():
    items = [{"name": "Milk", "price": 2.50}, {"name": "Bread", "price": 1.80}]
    expense = _make_expense(amount=4.30, amount_eur=4.30, source="receipt")
    pending = PendingExpense(expense=expense, display_text="", items=items)

    display = await _build_receipt_display(pending)
    assert "4.30" in display
    assert "Milk" in display
    assert "Bread" in display


@pytest.mark.asyncio
async def test_build_receipt_display_foreign_currency():
    items = [{"name": "Item", "price": 100.0}]
    expense = _make_expense(
        amount=200.0,
        amount_eur=50.0,
        original_currency="TRY",
        exchange_rate=4.0,
        source="receipt",
    )
    pending = PendingExpense(expense=expense, display_text="", items=items)

    display = await _build_receipt_display(pending)
    # 100 TRY * (50/200) = 25 EUR
    assert "25.00" in display
    assert "100.00 TRY" in display
