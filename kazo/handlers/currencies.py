import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from kazo.services.currency_service import (
    InvalidCurrencyError,
    get_rate_to_eur,
    get_recently_used_currencies,
    get_supported_currencies,
)

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("rate"))
async def cmd_rate(message: Message) -> None:
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        recent = await get_recently_used_currencies(message.chat.id)
        if not recent:
            await message.answer(
                "Usage: /rate USD\n\n"
                f"Supported: {', '.join(get_supported_currencies())}"
            )
            return

        lines: list[str] = []
        for code in recent:
            try:
                rate = await get_rate_to_eur(code)
                lines.append(f"1 {code} = {rate:.4f} EUR")
            except Exception:
                logger.warning("Failed to fetch rate for %s", code)
                lines.append(f"1 {code} = unavailable")

        await message.answer(
            "Recently used currencies:\n" + "\n".join(lines)
        )
        return

    currency = parts[1].strip().upper()

    try:
        rate = await get_rate_to_eur(currency)
    except InvalidCurrencyError as exc:
        await message.answer(str(exc))
        return
    except Exception:
        logger.exception("Failed to fetch rate for %s", currency)
        await message.answer(f"Could not fetch rate for {currency}. Try again later.")
        return

    if currency == "EUR":
        await message.answer("1 EUR = 1 EUR")
    else:
        inverse = 1.0 / rate if rate else 0
        await message.answer(
            f"1 {currency} = {rate:.4f} EUR\n"
            f"1 EUR = {inverse:.4f} {currency}"
        )
