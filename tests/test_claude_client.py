import json
from unittest.mock import AsyncMock, patch

import pytest

from kazo.claude.client import ask_claude, ask_claude_structured, _run_claude, _run_claude_once


def _mock_proc(stdout: bytes, returncode: int = 0, stderr: bytes = b""):
    proc = AsyncMock()
    proc.communicate.return_value = (stdout, stderr)
    proc.returncode = returncode
    proc.kill = AsyncMock()
    proc.wait = AsyncMock()
    return proc


@patch("kazo.claude.client.asyncio.create_subprocess_exec")
async def test_ask_claude_returns_result(mock_exec):
    payload = json.dumps({"result": "Hello"}).encode()
    mock_exec.return_value = _mock_proc(payload)

    result = await ask_claude("hi")
    assert result == "Hello"


@patch("kazo.claude.client.asyncio.create_subprocess_exec")
async def test_ask_claude_structured_returns_parsed(mock_exec):
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


@patch("kazo.claude.client.asyncio.create_subprocess_exec")
async def test_missing_structured_output_raises(mock_exec):
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

    result = await _run_claude(["-p", "test"])
    assert result == {"result": "ok"}
    assert mock_exec.call_count == 2


@patch("kazo.claude.client.asyncio.sleep", new_callable=AsyncMock)
@patch("kazo.claude.client.asyncio.create_subprocess_exec")
async def test_retry_exhausted_raises(mock_exec, mock_sleep):
    fail_proc = _mock_proc(b"", returncode=1, stderr=b"persistent")
    mock_exec.return_value = fail_proc

    with pytest.raises(RuntimeError, match="persistent"):
        await _run_claude(["-p", "test"])
    assert mock_exec.call_count == 2
