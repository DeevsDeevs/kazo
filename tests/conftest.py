import os

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token-000")

import aiosqlite
import pytest

import kazo.db.database as db_mod


@pytest.fixture(autouse=True)
async def test_db(monkeypatch):
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys=ON")
    await conn.executescript(db_mod.SCHEMA)
    await conn.commit()

    async def _get_db():
        return conn

    monkeypatch.setattr(db_mod, "get_db", _get_db)
    monkeypatch.setattr(db_mod, "_db", conn)

    yield conn

    await conn.close()
