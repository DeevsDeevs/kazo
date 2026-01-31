from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from kazo.db.models import Expense
from kazo.services.expense_service import get_expense_by_id, save_expense, update_expense


def _make_expense(**overrides) -> Expense:
    defaults = dict(
        id=None,
        chat_id=1,
        user_id=100,
        store="TestStore",
        amount=25.0,
        original_currency="EUR",
        amount_eur=25.0,
        exchange_rate=1.0,
        category="groceries",
        items_json=None,
        source="text",
        expense_date=date(2025, 3, 15),
        note=None,
    )
    defaults.update(overrides)
    return Expense(**defaults)


async def test_save_expense_with_note():
    exp_id = await save_expense(_make_expense(note="Birthday gift"))
    result = await get_expense_by_id(exp_id)
    assert result["note"] == "Birthday gift"


async def test_save_expense_without_note():
    exp_id = await save_expense(_make_expense())
    result = await get_expense_by_id(exp_id)
    assert result["note"] is None


async def test_update_expense_note():
    exp_id = await save_expense(_make_expense())
    updated = await update_expense(exp_id, note="Added later")
    assert updated is True
    result = await get_expense_by_id(exp_id)
    assert result["note"] == "Added later"


async def test_update_expense_note_overwrite():
    exp_id = await save_expense(_make_expense(note="Original"))
    await update_expense(exp_id, note="Updated")
    result = await get_expense_by_id(exp_id)
    assert result["note"] == "Updated"


async def test_cmd_note_last_expense():
    exp_id = await save_expense(_make_expense())
    message = MagicMock()
    message.text = "/note anniversary dinner"
    message.chat = MagicMock()
    message.chat.id = 1
    message.answer = AsyncMock()

    with patch("kazo.handlers.common.get_base_currency", return_value="EUR"):
        from kazo.handlers.common import cmd_note

        await cmd_note(message)

    message.answer.assert_called_once()
    call_text = message.answer.call_args[0][0]
    assert "anniversary dinner" in call_text

    result = await get_expense_by_id(exp_id)
    assert result["note"] == "anniversary dinner"


async def test_cmd_note_by_id():
    exp_id = await save_expense(_make_expense())
    message = MagicMock()
    message.text = f"/note {exp_id} work lunch"
    message.chat = MagicMock()
    message.chat.id = 1
    message.answer = AsyncMock()

    from kazo.handlers.common import cmd_note

    await cmd_note(message)

    result = await get_expense_by_id(exp_id)
    assert result["note"] == "work lunch"


async def test_cmd_note_no_args():
    message = MagicMock()
    message.text = "/note"
    message.chat = MagicMock()
    message.chat.id = 1
    message.answer = AsyncMock()

    from kazo.handlers.common import cmd_note

    await cmd_note(message)

    assert "Usage" in message.answer.call_args[0][0]
