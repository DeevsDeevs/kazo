import aiosqlite

from kazo.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    store TEXT,
    amount REAL NOT NULL CHECK(amount > 0),
    original_currency TEXT NOT NULL,
    amount_eur REAL NOT NULL CHECK(amount_eur > 0),
    exchange_rate REAL NOT NULL CHECK(exchange_rate > 0),
    category TEXT,
    items_json TEXT,
    source TEXT NOT NULL,
    expense_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    amount REAL NOT NULL CHECK(amount > 0),
    original_currency TEXT NOT NULL,
    amount_eur REAL NOT NULL CHECK(amount_eur > 0),
    frequency TEXT NOT NULL DEFAULT 'monthly' CHECK(frequency IN ('daily', 'weekly', 'monthly', 'yearly')),
    category TEXT,
    active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exchange_rates (
    currency TEXT PRIMARY KEY,
    rate_to_eur REAL NOT NULL CHECK(rate_to_eur > 0),
    fetched_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS custom_categories (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    UNIQUE(chat_id, name)
);

CREATE INDEX IF NOT EXISTS idx_expenses_chat_date ON expenses(chat_id, expense_date);
CREATE INDEX IF NOT EXISTS idx_expenses_chat_created ON expenses(chat_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_subscriptions_chat_active ON subscriptions(chat_id, active);
"""

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(settings.db_path)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def close_db():
    global _db
    if _db is not None:
        await _db.close()
        _db = None


async def init_db():
    db = await get_db()
    await db.executescript(SCHEMA)
    await db.commit()
