import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kazo.claude.client import (
    _ask_sdk,
    _ask_sdk_structured,
    _run_claude_once,
    _run_cli,
    ask_claude,
    ask_claude_structured,
)


def _mock_proc(stdout: bytes, returncode: int = 0, stderr: bytes = b""):
    proc = AsyncMock()
    proc.communicate.return_value = (stdout, stderr)
    proc.returncode = returncode
    proc.kill = AsyncMock()
    proc.wait = AsyncMock()
    return proc


# --- CLI backend tests ---


@patch("kazo.claude.client._use_sdk", return_value=False)
@patch("kazo.claude.client.asyncio.create_subprocess_exec")
async def test_ask_claude_cli_returns_result(mock_exec, _):
    payload = json.dumps({"result": "Hello"}).encode()
    mock_exec.return_value = _mock_proc(payload)

    result = await ask_claude("hi")
    assert result == "Hello"


@patch("kazo.claude.client._use_sdk", return_value=False)
@patch("kazo.claude.client.asyncio.create_subprocess_exec")
async def test_ask_claude_structured_cli_returns_parsed(mock_exec, _):
    payload = json.dumps({"structured_output": {"amount": 50}}).encode()
    mock_exec.return_value = _mock_proc(payload)

    result = await ask_claude_structured("50 groceries", {"type": "object"})
    assert result == {"amount": 50}


@patch("kazo.claude.client.asyncio.create_subprocess_exec")
async def test_nonzero_exit_raises(mock_exec):
    mock_exec.return_value = _mock_proc(b"", returncode=1, stderr=b"error")

    with pytest.raises(RuntimeError, match="Claude CLI error"):
        await _run_claude_once(["-p", "test"], timeout=30)


@patch("kazo.claude.client.asyncio.create_subprocess_exec")
async def test_invalid_json_raises(mock_exec):
    mock_exec.return_value = _mock_proc(b"not json")

    with pytest.raises(RuntimeError, match="non-JSON"):
        await _run_claude_once(["-p", "test"], timeout=30)


@patch("kazo.claude.client._use_sdk", return_value=False)
@patch("kazo.claude.client.asyncio.create_subprocess_exec")
async def test_missing_structured_output_raises(mock_exec, _):
    payload = json.dumps({"result": "text only"}).encode()
    mock_exec.return_value = _mock_proc(payload)

    with pytest.raises(RuntimeError, match="no structured output"):
        await ask_claude_structured("test", {"type": "object"})


@patch("kazo.claude.client.asyncio.sleep", new_callable=AsyncMock)
@patch("kazo.claude.client.asyncio.create_subprocess_exec")
async def test_retry_succeeds_on_second_attempt(mock_exec, mock_sleep):
    fail_proc = _mock_proc(b"", returncode=1, stderr=b"transient")
    ok_payload = json.dumps({"result": "ok"}).encode()
    ok_proc = _mock_proc(ok_payload)
    mock_exec.side_effect = [fail_proc, ok_proc]

    result = await _run_cli(["-p", "test"])
    assert result == {"result": "ok"}
    assert mock_exec.call_count == 2


@patch("kazo.claude.client.asyncio.sleep", new_callable=AsyncMock)
@patch("kazo.claude.client.asyncio.create_subprocess_exec")
async def test_retry_exhausted_raises(mock_exec, mock_sleep):
    fail_proc = _mock_proc(b"", returncode=1, stderr=b"persistent")
    mock_exec.return_value = fail_proc

    with pytest.raises(RuntimeError, match="persistent"):
        await _run_cli(["-p", "test"])
    assert mock_exec.call_count == 2


# --- SDK backend tests ---


def _mock_text_response(text: str):
    block = MagicMock()
    block.text = text
    block.type = "text"
    response = MagicMock()
    response.content = [block]
    return response


def _mock_tool_use_response(tool_input: dict, tool_name: str = "structured_output"):
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    response = MagicMock()
    response.content = [block]
    return response


@patch("kazo.claude.client._get_api_client")
async def test_ask_sdk_returns_text(mock_get_client):
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = _mock_text_response("Hello from SDK")
    mock_get_client.return_value = mock_client

    result = await _ask_sdk("hi")
    assert result == "Hello from SDK"


@patch("kazo.claude.client._get_api_client")
async def test_ask_sdk_passes_system_prompt(mock_get_client):
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = _mock_text_response("ok")
    mock_get_client.return_value = mock_client

    await _ask_sdk("hi", system_prompt="be nice")
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["system"] == "be nice"


@patch("kazo.claude.client._get_api_client")
async def test_ask_sdk_structured_returns_tool_input(mock_get_client):
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = _mock_tool_use_response({"amount": 42.0, "category": "food"})
    mock_get_client.return_value = mock_client

    result = await _ask_sdk_structured("42 on food", {"type": "object"})
    assert result == {"amount": 42.0, "category": "food"}


@patch("kazo.claude.client._get_api_client")
async def test_ask_sdk_structured_with_image(mock_get_client):
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = _mock_tool_use_response({"total": 10.0})
    mock_get_client.return_value = mock_client

    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"\xff\xd8\xff\xe0fake jpeg")
        tmp_path = f.name

    try:
        result = await _ask_sdk_structured("parse receipt", {"type": "object"}, image_path=tmp_path)
        assert result == {"total": 10.0}
        call_kwargs = mock_client.messages.create.call_args[1]
        content = call_kwargs["messages"][0]["content"]
        assert content[0]["type"] == "image"
        assert content[1]["type"] == "text"
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@patch("kazo.claude.client._get_api_client")
async def test_ask_sdk_structured_no_tool_use_raises(mock_get_client):
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = _mock_text_response("no tool use here")
    mock_get_client.return_value = mock_client

    with pytest.raises(RuntimeError, match="no tool_use block"):
        await _ask_sdk_structured("test", {"type": "object"})


# --- Router tests ---


@patch("kazo.claude.client._use_sdk", return_value=True)
@patch("kazo.claude.client._ask_sdk", new_callable=AsyncMock, return_value="sdk result")
async def test_ask_claude_routes_to_sdk(mock_sdk, _):
    result = await ask_claude("hi")
    assert result == "sdk result"
    mock_sdk.assert_called_once_with("hi", "")


@patch("kazo.claude.client._use_sdk", return_value=False)
@patch("kazo.claude.client._ask_cli", new_callable=AsyncMock, return_value="cli result")
async def test_ask_claude_routes_to_cli(mock_cli, _):
    result = await ask_claude("hi")
    assert result == "cli result"
    mock_cli.assert_called_once_with("hi", "")
