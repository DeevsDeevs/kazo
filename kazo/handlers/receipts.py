import json
import logging
import tempfile
from datetime import date, datetime
from pathlib import Path

from aiogram import Bot, Router, F
from aiogram.types import Message

from kazo.categories import get_categories_str
from kazo.claude.client import ask_claude_structured
from kazo.db.models import Expense
from kazo.services.currency_service import convert_to_eur
from kazo.services.expense_service import save_expense

logger = logging.getLogger(__name__)
router = Router()

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

RECEIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "store": {"type": ["string", "null"]},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "price": {"type": "number"},
                },
                "required": ["name", "price"],
            },
        },
        "total": {"type": "number"},
        "currency": {"type": "string"},
        "category": {"type": "string"},
        "expense_date": {"type": "string"},
    },
    "required": ["total", "currency", "category", "expense_date"],
}

SUPPORTED_DOC_MIMES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}

MIME_TO_SUFFIX = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
}


async def _parse_and_save_receipt(message: Message, bot: Bot, file_id: str, suffix: str):
    """Download a file, parse it as a receipt via Claude, and save the expense."""
    file = await bot.get_file(file_id)

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name
            await bot.download_file(file.file_path, tmp)

        categories_str = await get_categories_str(message.chat.id)
        system_prompt = (PROMPTS_DIR / "parse_receipt.txt").read_text().format(
            categories=categories_str,
            today=date.today().isoformat(),
        )

        parsed = await ask_claude_structured(
            prompt="Extract all information from this receipt.",
            json_schema=RECEIPT_SCHEMA,
            system_prompt=system_prompt,
            image_path=tmp_path,
        )
    except Exception:
        logger.exception("Failed to parse receipt")
        await message.answer("Sorry, I couldn't read that receipt. Try a clearer image.")
        return
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

    try:
        total = parsed["total"]
        currency = parsed["currency"].upper()
        category = parsed["category"].lower()
    except (KeyError, AttributeError):
        logger.exception("Malformed Claude response: %s", parsed)
        await message.answer("Sorry, I couldn't parse that receipt properly. Please try again.")
        return

    if not total or total <= 0:
        await message.answer("Couldn't determine a valid total. Please try again.")
        return

    store = parsed.get("store")
    items = parsed.get("items", [])
    expense_date = parsed.get("expense_date", date.today().isoformat())

    if items:
        items_sum = sum(i.get("price", 0) for i in items)
        if items_sum > 0 and abs(items_sum - total) / total > 0.1:
            logger.warning(
                "Receipt total %.2f doesn't match items sum %.2f (diff > 10%%)",
                total, items_sum,
            )

    amount_eur, rate = await convert_to_eur(total, currency)

    expense = Expense(
        id=None,
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        store=store,
        amount=total,
        original_currency=currency,
        amount_eur=amount_eur,
        exchange_rate=rate,
        category=category,
        items_json=json.dumps(items) if items else None,
        source="receipt",
        expense_date=expense_date,
    )

    await save_expense(expense)

    items_text = ""
    if items:
        items_lines = [f"  • {i['name']}: {i['price']:.2f}" for i in items[:10]]
        items_text = "\n" + "\n".join(items_lines)

    currency_note = f" ({total} {currency})" if currency != "EUR" else ""

    await message.answer(
        f"🧾 Receipt processed\n"
        f"💰 €{amount_eur:.2f}{currency_note}\n"
        f"🏷 {category}\n"
        f"📅 {expense_date}"
        + (f"\n🏪 {store}" if store else "")
        + items_text
    )


@router.message(F.photo)
async def handle_receipt_photo(message: Message, bot: Bot):
    if not message.from_user:
        return

    await message.answer("Processing receipt...")
    photo = message.photo[-1]
    await _parse_and_save_receipt(message, bot, photo.file_id, ".jpg")


@router.message(F.document)
async def handle_receipt_document(message: Message, bot: Bot):
    if not message.from_user:
        return

    doc = message.document
    mime = doc.mime_type or ""

    if mime not in SUPPORTED_DOC_MIMES:
        return

    await message.answer("Processing receipt document...")
    suffix = MIME_TO_SUFFIX.get(mime, ".bin")
    await _parse_and_save_receipt(message, bot, doc.file_id, suffix)
