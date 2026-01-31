import json
from unittest.mock import AsyncMock, patch

import pytest

from kazo.main import _health_check


async def _call_health(mock_get_db=None):
    reader = AsyncMock()
    reader.read = AsyncMock(return_value=b"GET /health HTTP/1.1\r\n\r\n")
    writer = AsyncMock()
    written = bytearray()
    writer.write = lambda data: written.extend(data)
    writer.drain = AsyncMock()
    writer.close = AsyncMock()

    if mock_get_db:
        with patch("kazo.main.get_db", mock_get_db):
            await _health_check(reader, writer)
    else:
        await _health_check(reader, writer)

    raw = written.decode()
    body_start = raw.index("\r\n\r\n") + 4
    return raw[:body_start], json.loads(raw[body_start:])


@pytest.mark.asyncio
async def test_health_check_healthy():
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    async def fake_get_db():
        return mock_db

    headers, body = await _call_health(fake_get_db)
    assert "200 OK" in headers
    assert body["status"] == "healthy"
    assert body["checks"]["db"] == "ok"


@pytest.mark.asyncio
async def test_health_check_db_error():
    async def failing_db():
        raise ConnectionError("db gone")

    headers, body = await _call_health(failing_db)
    assert "503" in headers
    assert body["status"] == "unhealthy"
    assert "error" in body["checks"]["db"]
