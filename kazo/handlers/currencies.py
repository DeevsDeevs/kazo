import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from kazo.currency import get_base_currency, set_base_currency
from kazo.services.currency_service import (
    InvalidCurrencyError,
    get_rate,
    get_recently_used_currencies,
    get_supported_currencies,
    validate_currency,
)

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("rate"))
async def cmd_rate(message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    base = await get_base_currency(message.chat.id)

    if len(parts) < 2 or not parts[1].strip():
        recent = await get_recently_used_currencies(message.chat.id)
        if not recent:
            await message.answer(f"Usage: /rate USD\n\nSupported: {', '.join(get_supported_currencies())}")
            return

        lines: list[str] = []
        for code in recent:
            try:
                rate = await get_rate(code, base)
                lines.append(f"1 {code} = {rate:.4f} {base}")
            except Exception:
                logger.warning("Failed to fetch rate for %s", code, extra={"chat_id": message.chat.id})
                lines.append(f"1 {code} = unavailable")

        await message.answer("Recently used currencies:\n" + "\n".join(lines))
        return

    currency = parts[1].strip().upper()

    try:
        rate = await get_rate(currency, base)
    except InvalidCurrencyError as exc:
        await message.answer(str(exc))
        return
    except Exception:
        logger.exception("Failed to fetch rate for %s", currency, extra={"chat_id": message.chat.id})
        await message.answer(f"Could not fetch rate for {currency}. Try again later.")
        return

    if currency == base:
        await message.answer(f"1 {base} = 1 {base}")
    else:
        inverse = 1.0 / rate if rate else 0
        await message.answer(f"1 {currency} = {rate:.4f} {base}\n1 {base} = {inverse:.4f} {currency}")


@router.message(Command("setcurrency"))
async def cmd_setcurrency(message: Message) -> None:
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2 or not parts[1].strip():
        base = await get_base_currency(message.chat.id)
        await message.answer(
            f"Current base currency: {base}\n\n"
            f"Usage: /setcurrency USD\n"
            f"Supported: {', '.join(get_supported_currencies())}"
        )
        return

    code = parts[1].strip().upper()
    try:
        code = validate_currency(code)
    except InvalidCurrencyError as exc:
        await message.answer(str(exc))
        return

    await set_base_currency(message.chat.id, code)
    await message.answer(f"Base currency set to {code}. All amounts will now display in {code}.")


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    from kazo.config import settings

    base = await get_base_currency(message.chat.id)
    backend = "API (SDK)" if settings.anthropic_api_key else "CLI"
    await message.answer(
        f"⚙️ Settings\n\n"
        f"Base currency: {base}\n"
        f"Backend: {backend}\n"
        f"Model: {settings.claude_model}\n"
        f"\nUse /setcurrency to change base currency."
    )
