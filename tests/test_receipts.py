from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kazo.handlers.receipts import (
    SUPPORTED_DOC_MIMES,
    handle_receipt_document,
    handle_receipt_photo,
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


MOCK_CLASSIFY_RECEIPT = {"type": "receipt"}
MOCK_CLASSIFY_PRODUCT = {"type": "product"}

MOCK_PARSED = {
    "store": "TestMart",
    "items": [{"name": "Milk", "price": 2.50}],
    "total": 2.50,
    "currency": "EUR",
    "category": "groceries",
    "expense_date": "2025-01-15",
}

MOCK_PRODUCTS = {
    "products": [{"name": "Tomatoes", "quantity": 1}, {"name": "Bread", "quantity": 1}],
    "category": "groceries",
    "description": "Groceries",
}


@patch("kazo.handlers.receipts.store_pending", new_callable=AsyncMock)
@patch("kazo.handlers.receipts.convert_to_base", new_callable=AsyncMock, return_value=(2.50, 1.0))
@patch("kazo.handlers.receipts.get_base_currency", new_callable=AsyncMock, return_value="EUR")
@patch("kazo.handlers.receipts.ask_claude_structured", new_callable=AsyncMock)
@patch("kazo.handlers.receipts.get_categories_str", new_callable=AsyncMock, return_value="groceries, dining")
async def test_photo_handler(mock_cats, mock_claude, mock_base, mock_convert, mock_pending):
    mock_claude.side_effect = [MOCK_CLASSIFY_RECEIPT, MOCK_PARSED]
    msg = _make_message()
    bot = _make_bot()
    photo = MagicMock()
    photo.file_id = "photo123"
    msg.photo = [photo]

    await handle_receipt_photo(msg, bot)

    assert mock_claude.call_count == 2
    mock_pending.assert_called_once()


@patch("kazo.handlers.receipts.store_pending", new_callable=AsyncMock)
@patch("kazo.handlers.receipts.convert_to_base", new_callable=AsyncMock, return_value=(10.0, 1.0))
@patch("kazo.handlers.receipts.get_base_currency", new_callable=AsyncMock, return_value="EUR")
@patch("kazo.handlers.receipts.ask_claude_structured", new_callable=AsyncMock)
@patch("kazo.handlers.receipts.get_categories_str", new_callable=AsyncMock, return_value="groceries")
async def test_document_handler_pdf(mock_cats, mock_claude, mock_base, mock_convert, mock_pending):
    mock_claude.side_effect = [MOCK_CLASSIFY_RECEIPT, {**MOCK_PARSED, "total": 10.0}]
    msg = _make_message()
    bot = _make_bot()
    doc = MagicMock()
    doc.file_id = "doc123"
    doc.mime_type = "application/pdf"
    msg.document = doc

    await handle_receipt_document(msg, bot)

    assert mock_claude.call_count == 2
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


@patch("kazo.handlers.receipts.ask_claude_structured", new_callable=AsyncMock)
@patch("kazo.handlers.receipts.get_categories_str", new_callable=AsyncMock, return_value="groceries")
async def test_document_handler_claude_error(mock_cats, mock_claude):
    mock_claude.side_effect = RuntimeError("fail")
    msg = _make_message()
    bot = _make_bot()
    doc = MagicMock()
    doc.file_id = "doc123"
    doc.mime_type = "image/png"
    msg.document = doc

    await handle_receipt_document(msg, bot)

    assert any("couldn't process" in str(call) for call in msg.answer.call_args_list)


@patch("kazo.handlers.receipts.ask_claude_structured", new_callable=AsyncMock)
@patch("kazo.handlers.receipts.get_categories_str", new_callable=AsyncMock, return_value="groceries")
async def test_photo_classified_as_product(mock_cats, mock_claude):
    mock_claude.side_effect = [MOCK_CLASSIFY_PRODUCT, MOCK_PRODUCTS]
    msg = _make_message()
    bot = _make_bot()
    photo = MagicMock()
    photo.file_id = "photo123"
    msg.photo = [photo]

    await handle_receipt_photo(msg, bot)

    assert mock_claude.call_count == 2
    # Should show product list, not store_pending
    answer_text = msg.answer.call_args_list[-1].args[0]
    assert "Tomatoes" in answer_text
    assert "Bread" in answer_text


@patch("kazo.handlers.receipts.ask_claude_structured", new_callable=AsyncMock)
async def test_photo_classified_as_other(mock_claude):
    mock_claude.return_value = {"type": "other"}
    msg = _make_message()
    bot = _make_bot()
    photo = MagicMock()
    photo.file_id = "photo123"
    msg.photo = [photo]

    await handle_receipt_photo(msg, bot)

    assert any("not sure" in str(call) for call in msg.answer.call_args_list)


@patch("kazo.handlers.receipts.store_pending", new_callable=AsyncMock)
@patch("kazo.handlers.receipts.convert_to_base", new_callable=AsyncMock, return_value=(45.0, 1.0))
@patch("kazo.handlers.receipts.get_base_currency", new_callable=AsyncMock, return_value="EUR")
@patch("kazo.handlers.receipts.ask_claude_structured", new_callable=AsyncMock)
@patch("kazo.handlers.receipts.get_categories_str", new_callable=AsyncMock, return_value="groceries")
async def test_product_price_reply(mock_cats, mock_claude, mock_base, mock_convert, mock_pending):
    import time

    from kazo.handlers.receipts import _product_sessions, handle_product_price_reply

    bot_msg_id = 999
    _product_sessions[bot_msg_id] = {
        "chat_id": 1,
        "user_id": 1,
        "products": [{"name": "Tomatoes", "quantity": 1}],
        "category": "groceries",
        "description": "Groceries",
        "bot_message_id": bot_msg_id,
        "created_at": time.monotonic(),
    }

    mock_claude.return_value = {
        "items": [{"name": "Tomatoes", "price": 3.50, "quantity": 1}],
        "total": 3.50,
        "currency": "EUR",
    }

    msg = _make_message()
    msg.text = "3.50 euros"
    msg.reply_to_message = MagicMock()
    msg.reply_to_message.message_id = bot_msg_id

    await handle_product_price_reply(msg)

    mock_pending.assert_called_once()
    expense = mock_pending.call_args.args[1]
    assert expense.amount == 3.50
    assert expense.source == "product_photo"

    assert bot_msg_id not in _product_sessions


@patch("kazo.handlers.receipts.ask_claude_structured", new_callable=AsyncMock)
async def test_product_price_reply_no_session(mock_claude):
    from kazo.handlers.receipts import handle_product_price_reply

    msg = _make_message()
    msg.text = "45 euros"
    msg.reply_to_message = MagicMock()
    msg.reply_to_message.message_id = 12345

    await handle_product_price_reply(msg)

    mock_claude.assert_not_called()
