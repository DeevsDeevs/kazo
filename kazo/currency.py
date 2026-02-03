from kazo.config import settings
from kazo.db.database import get_db

CURRENCY_SYMBOLS: dict[str, str] = {
    "EUR": "\u20ac",
    "USD": "$",
    "GBP": "\u00a3",
    "JPY": "\u00a5",
    "CHF": "CHF",
    "SEK": "kr",
    "NOK": "kr",
    "DKK": "kr",
    "PLN": "z\u0142",
    "CZK": "K\u010d",
    "HUF": "Ft",
    "RON": "lei",
    "RUB": "₽",
    "BGN": "лв",
    "TRY": "\u20ba",
    "BRL": "R$",
    "CAD": "C$",
    "AUD": "A$",
    "NZD": "NZ$",
    "INR": "\u20b9",
    "KRW": "\u20a9",
    "CNY": "\u00a5",
    "HKD": "HK$",
    "SGD": "S$",
    "MXN": "MX$",
    "ZAR": "R",
    "ILS": "\u20aa",
    "THB": "\u0e3f",
    "PHP": "\u20b1",
    "MYR": "RM",
    "IDR": "Rp",
    "ISK": "kr",
}


def currency_symbol(code: str) -> str:
    return CURRENCY_SYMBOLS.get(code, code)


def format_amount(amount: float, currency_code: str) -> str:
    sym = currency_symbol(currency_code)
    if sym in ("\u20ac", "$", "\u00a3", "\u00a5", "\u20b9", "\u20a9", "\u20ba", "\u20aa", "\u20b1", "₽"):
        return f"{sym}{amount:.2f}"
    return f"{amount:.2f} {sym}"


async def get_base_currency(chat_id: int) -> str:
    db = await get_db()
    cursor = await db.execute(
        "SELECT base_currency FROM chat_settings WHERE chat_id = ?",
        (chat_id,),
    )
    row = await cursor.fetchone()
    if row:
        return row["base_currency"]
    return settings.base_currency


async def set_base_currency(chat_id: int, currency: str) -> None:
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO chat_settings (chat_id, base_currency) VALUES (?, ?)",
        (chat_id, currency.upper()),
    )
    await db.commit()
