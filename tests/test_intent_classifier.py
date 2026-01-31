from unittest.mock import AsyncMock, MagicMock, patch

from kazo.handlers.common import _classify_intent, _handle_conversational_intent, handle_text_expense


def _make_message(text, has_user=True):
    msg = AsyncMock()
    msg.text = text
    msg.chat = MagicMock(id=1)
    msg.from_user = MagicMock(id=100) if has_user else None
    msg.answer = AsyncMock()
    msg.reply_to_message = None
    return msg


@patch("kazo.handlers.common.ask_claude_structured")
async def test_classify_intent_calls_claude(mock_claude):
    mock_claude.return_value = {"intent": "undo"}
    result = await _classify_intent("undo that")
    assert result["intent"] == "undo"
    mock_claude.assert_called_once()


@patch("kazo.handlers.common.ask_claude_structured")
async def test_classify_intent_returns_args(mock_claude):
    mock_claude.return_value = {"intent": "price", "args": "tomatoes"}
    result = await _classify_intent("how much were tomatoes")
    assert result["args"] == "tomatoes"


@patch("kazo.handlers.common.cmd_undo", new_callable=AsyncMock)
async def test_conversational_undo(mock_undo):
    msg = _make_message("undo that")
    await _handle_conversational_intent(msg, "undo", None)
    mock_undo.assert_called_once_with(msg)


@patch("kazo.handlers.common.cmd_start", new_callable=AsyncMock)
async def test_conversational_help(mock_start):
    msg = _make_message("what can you do?")
    await _handle_conversational_intent(msg, "help", None)
    mock_start.assert_called_once_with(msg)


@patch("kazo.handlers.common.ask_claude")
async def test_conversational_chat(mock_claude):
    mock_claude.return_value = "Hello! I'm Kazo."
    msg = _make_message("hello")
    await _handle_conversational_intent(msg, "chat", None)
    msg.answer.assert_called_once_with("Hello! I'm Kazo.")


@patch("kazo.handlers.common._classify_intent")
async def test_no_number_triggers_classifier(mock_classify):
    mock_classify.return_value = {"intent": "chat"}
    msg = _make_message("hello there")
    with patch("kazo.handlers.common.ask_claude", return_value="Hi!"):
        await handle_text_expense(msg)
    mock_classify.assert_called_once()


@patch("kazo.handlers.common.ask_claude_structured")
async def test_number_skips_classifier(mock_structured):
    mock_structured.return_value = {
        "amount": 50,
        "currency": "EUR",
        "category": "groceries",
        "description": "Groceries",
        "expense_date": "2025-03-15",
    }
    msg = _make_message("spent 50 on groceries")
    with (
        patch("kazo.handlers.common.store_pending", new_callable=AsyncMock),
        patch("kazo.handlers.common.convert_to_base", new_callable=AsyncMock, return_value=(50.0, 1.0)),
        patch("kazo.handlers.common.get_base_currency", new_callable=AsyncMock, return_value="EUR"),
        patch("kazo.handlers.common.get_categories", return_value=["groceries"]),
    ):
        await handle_text_expense(msg)
    # Should have called structured (expense parser), not intent classifier
    assert mock_structured.call_count == 1
    call_system = mock_structured.call_args.kwargs.get("system_prompt", "")
    assert "intent" not in call_system.lower() or "expense" in call_system.lower()


@patch("kazo.handlers.common._classify_intent")
async def test_classifier_error_silently_ignored(mock_classify):
    mock_classify.side_effect = RuntimeError("Claude error")
    msg = _make_message("hello")
    await handle_text_expense(msg)
    msg.answer.assert_not_called()
