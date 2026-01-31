from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from kazo.handlers.receipts import (
    handle_receipt_document,
    handle_receipt_photo,
    SUPPORTED_DOC_MIMES,
)


def _make_message(chat_id=1, user_id=1):
    msg = AsyncMock()
    msg.chat.id = chat_id
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    return msg


def _make_bot(file_path="photos/file.jpg"):
    bot = AsyncMock()
    file_obj = MagicMock()
    file_obj.file_path = file_path
    bot.get_file.return_value = file_obj
    return bot


MOCK_PARSED = {
    "store": "TestMart",
    "items": [{"name": "Milk", "price": 2.50}],
    "total": 2.50,
    "currency": "EUR",
    "category": "groceries",
    "expense_date": "2025-01-15",
}


@patch("kazo.handlers.receipts.store_pending", new_callable=AsyncMock)
@patch("kazo.handlers.receipts.convert_to_eur", new_callable=AsyncMock, return_value=(2.50, 1.0))
@patch("kazo.handlers.receipts.ask_claude_structured", new_callable=AsyncMock, return_value=MOCK_PARSED)
@patch("kazo.handlers.receipts.get_categories_str", new_callable=AsyncMock, return_value="groceries, dining")
async def test_photo_handler(mock_cats, mock_claude, mock_convert, mock_pending):
    msg = _make_message()
    bot = _make_bot()
    photo = MagicMock()
    photo.file_id = "photo123"
    msg.photo = [photo]

    await handle_receipt_photo(msg, bot)

    mock_claude.assert_called_once()
    mock_pending.assert_called_once()


@patch("kazo.handlers.receipts.store_pending", new_callable=AsyncMock)
@patch("kazo.handlers.receipts.convert_to_eur", new_callable=AsyncMock, return_value=(10.0, 1.0))
@patch("kazo.handlers.receipts.ask_claude_structured", new_callable=AsyncMock, return_value={**MOCK_PARSED, "total": 10.0})
@patch("kazo.handlers.receipts.get_categories_str", new_callable=AsyncMock, return_value="groceries")
async def test_document_handler_pdf(mock_cats, mock_claude, mock_convert, mock_pending):
    msg = _make_message()
    bot = _make_bot()
    doc = MagicMock()
    doc.file_id = "doc123"
    doc.mime_type = "application/pdf"
    msg.document = doc

    await handle_receipt_document(msg, bot)

    mock_claude.assert_called_once()
    mock_pending.assert_called_once()


async def test_document_handler_unsupported_mime():
    msg = _make_message()
    bot = _make_bot()
    doc = MagicMock()
    doc.mime_type = "text/plain"
    msg.document = doc

    await handle_receipt_document(msg, bot)

    msg.answer.assert_not_called()


async def test_document_handler_no_user():
    msg = AsyncMock()
    msg.from_user = None
    bot = _make_bot()

    await handle_receipt_document(msg, bot)
    msg.answer.assert_not_called()


@pytest.mark.parametrize("mime", list(SUPPORTED_DOC_MIMES))
async def test_all_supported_mimes_accepted(mime):
    assert mime in SUPPORTED_DOC_MIMES


@patch("kazo.handlers.receipts.ask_claude_structured", new_callable=AsyncMock, side_effect=RuntimeError("fail"))
@patch("kazo.handlers.receipts.get_categories_str", new_callable=AsyncMock, return_value="groceries")
async def test_document_handler_claude_error(mock_cats, mock_claude):
    msg = _make_message()
    bot = _make_bot()
    doc = MagicMock()
    doc.file_id = "doc123"
    doc.mime_type = "image/png"
    msg.document = doc

    await handle_receipt_document(msg, bot)

    assert any("couldn't read" in str(call) for call in msg.answer.call_args_list)
