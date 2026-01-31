import json
import logging
import tempfile
import time
from datetime import date
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from kazo.categories import get_categories_str
from kazo.claude.client import ask_claude_structured
from kazo.currency import format_amount, get_base_currency
from kazo.db.models import Expense
from kazo.handlers.pending import store_pending
from kazo.services.currency_service import convert_to_base

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

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["receipt", "product", "other"]},
    },
    "required": ["type"],
}

PRODUCT_SCHEMA = {
    "type": "object",
    "properties": {
        "products": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "quantity": {"type": "number"},
                },
                "required": ["name", "quantity"],
            },
        },
        "category": {"type": "string"},
        "description": {"type": "string"},
    },
    "required": ["products", "category", "description"],
}

PRODUCT_PRICE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "price": {"type": "number"},
                    "quantity": {"type": "number"},
                },
                "required": ["name", "price"],
            },
        },
        "total": {"type": "number"},
        "currency": {"type": "string"},
    },
    "required": ["items", "total", "currency"],
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

PRODUCT_SESSION_TTL = 600  # 10 minutes

_product_sessions: dict[int, dict] = {}


def _cleanup_product_sessions():
    now = time.monotonic()
    expired = [k for k, v in _product_sessions.items() if now - v["created_at"] > PRODUCT_SESSION_TTL]
    for k in expired:
        del _product_sessions[k]


async def _classify_image(image_path: str) -> str:
    system_prompt = (PROMPTS_DIR / "classify_photo.txt").read_text()
    try:
        result = await ask_claude_structured(
            prompt="Classify this image.",
            json_schema=CLASSIFY_SCHEMA,
            system_prompt=system_prompt,
            image_path=image_path,
        )
        return result.get("type", "other")
    except Exception:
        logger.exception("Failed to classify image")
        return "receipt"  # default to receipt flow on error


async def _handle_receipt(message: Message, bot: Bot, image_path: str):
    base = await get_base_currency(message.chat.id)
    categories_str = await get_categories_str(message.chat.id)
    system_prompt = (
        (PROMPTS_DIR / "parse_receipt.txt")
        .read_text()
        .format(
            categories=categories_str,
            today=date.today().isoformat(),
            base_currency=base,
        )
    )

    parsed = await ask_claude_structured(
        prompt="Extract all information from this receipt.",
        json_schema=RECEIPT_SCHEMA,
        system_prompt=system_prompt,
        image_path=image_path,
        chat_id=message.chat.id,
    )

    try:
        total = parsed["total"]
        currency = parsed["currency"].upper()
        category = parsed["category"].lower()
    except (KeyError, AttributeError):
        logger.exception(
            "Malformed Claude response: %s", parsed, extra={"chat_id": message.chat.id, "handler": "receipt"}
        )
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
                total,
                items_sum,
                extra={"chat_id": message.chat.id, "handler": "receipt"},
            )

    amount_eur, rate = await convert_to_base(total, currency, message.chat.id)

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

    items_text = ""
    if items:
        items_lines = [
            f"  • {i['name']}: {i['price']:.2f}" if i.get("price") is not None else f"  • {i['name']}"
            for i in items[:10]
        ]
        items_text = "\n" + "\n".join(items_lines)

    currency_note = f" ({total} {currency})" if currency != base else ""

    display_text = (
        f"🧾 Receipt processed\n"
        f"💰 {format_amount(amount_eur, base)}{currency_note}\n"
        f"🏷 {category}\n"
        f"📅 {expense_date}" + (f"\n🏪 {store}" if store else "") + items_text
    )

    await store_pending(message, expense, display_text)


async def _handle_product_photo(message: Message, bot: Bot, image_path: str):
    categories_str = await get_categories_str(message.chat.id)
    system_prompt = (
        (PROMPTS_DIR / "identify_products.txt")
        .read_text()
        .format(
            categories=categories_str,
            today=date.today().isoformat(),
        )
    )

    parsed = await ask_claude_structured(
        prompt="Identify all products visible in this image.",
        json_schema=PRODUCT_SCHEMA,
        system_prompt=system_prompt,
        image_path=image_path,
        chat_id=message.chat.id,
    )

    products = parsed.get("products", [])
    if not products:
        await message.answer(
            "I couldn't identify any products in this image. Try a clearer photo or send a receipt instead."
        )
        return

    category = parsed.get("category", "other").lower()
    description = parsed.get("description", "Products")

    products_text = "\n".join(
        f"  • {p['name']}" + (f" (x{p['quantity']:.0f})" if p.get("quantity", 1) > 1 else "") for p in products
    )

    sent = await message.answer(
        f"📷 I see these products:\n{products_text}\n\n"
        f'Reply with the total (e.g., "45 euros") or per-item prices (e.g., "tomatoes 3.50, bread 2.20").',
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Cancel", callback_data="product:cancel"),
                ]
            ]
        ),
    )

    _cleanup_product_sessions()
    _product_sessions[sent.message_id] = {
        "chat_id": message.chat.id,
        "user_id": message.from_user.id,
        "products": products,
        "category": category,
        "description": description,
        "bot_message_id": sent.message_id,
        "created_at": time.monotonic(),
    }


async def _process_product_prices(message: Message, session: dict):
    base = await get_base_currency(message.chat.id)
    products_json = json.dumps(session["products"], indent=2)
    system_prompt = (
        (PROMPTS_DIR / "parse_product_prices.txt")
        .read_text()
        .format(
            products=products_json,
            user_input=message.text,
            base_currency=base,
        )
    )

    try:
        parsed = await ask_claude_structured(
            prompt=message.text,
            json_schema=PRODUCT_PRICE_SCHEMA,
            system_prompt=system_prompt,
            chat_id=message.chat.id,
        )
    except Exception:
        logger.exception(
            "Failed to parse product prices", extra={"chat_id": message.chat.id, "handler": "product_prices"}
        )
        await message.answer(
            'Sorry, I couldn\'t understand that. Try again with prices like "45 euros" or "tomatoes 3.50, bread 2.20".'
        )
        return

    items = parsed.get("items", [])
    total = parsed.get("total", 0)
    currency = parsed.get("currency", base).upper()

    if not total or total <= 0:
        await message.answer("Couldn't determine a valid total. Please try again.")
        return

    _product_sessions.pop(session["bot_message_id"], None)

    amount_eur, rate = await convert_to_base(total, currency, message.chat.id)

    expense = Expense(
        id=None,
        chat_id=session["chat_id"],
        user_id=session["user_id"],
        store=None,
        amount=total,
        original_currency=currency,
        amount_eur=amount_eur,
        exchange_rate=rate,
        category=session["category"],
        items_json=json.dumps(items) if items else None,
        source="product_photo",
        expense_date=date.today().isoformat(),
    )

    items_text = ""
    if items:
        items_lines = [
            f"  • {i['name']}: {i['price']:.2f}" if i.get("price") is not None else f"  • {i['name']}"
            for i in items[:10]
        ]
        items_text = "\n" + "\n".join(items_lines)

    currency_note = f" ({total} {currency})" if currency != base else ""

    display_text = (
        f"📷 {session['description']}\n"
        f"💰 {format_amount(amount_eur, base)}{currency_note}\n"
        f"🏷 {session['category']}\n"
        f"📅 {date.today().isoformat()}" + items_text
    )

    await store_pending(message, expense, display_text)


async def _parse_and_save(message: Message, bot: Bot, file_id: str, suffix: str):
    file = await bot.get_file(file_id)

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name
            await bot.download_file(file.file_path, tmp)

        image_type = await _classify_image(tmp_path)
        logger.info("Image classified as: %s", image_type, extra={"chat_id": message.chat.id, "handler": "photo"})

        if image_type == "product":
            await _handle_product_photo(message, bot, tmp_path)
        elif image_type == "receipt":
            await _handle_receipt(message, bot, tmp_path)
        else:
            await message.answer("I'm not sure what this is. Send a receipt photo or a picture of products you bought.")
    except Exception:
        logger.exception("Failed to process image", extra={"chat_id": message.chat.id, "handler": "photo"})
        await message.answer("Sorry, I couldn't process that image. Try a clearer photo.")
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


@router.message(F.reply_to_message & F.text & ~F.text.startswith("/"))
async def handle_product_price_reply(message: Message):
    if not message.reply_to_message:
        return

    reply_msg_id = message.reply_to_message.message_id
    session = _product_sessions.get(reply_msg_id)
    if not session:
        return
    if session["chat_id"] != message.chat.id:
        return

    await _process_product_prices(message, session)


@router.message(F.photo)
async def handle_receipt_photo(message: Message, bot: Bot):
    if not message.from_user:
        return

    await message.answer("Processing image...")
    photo = message.photo[-1]
    await _parse_and_save(message, bot, photo.file_id, ".jpg")


@router.message(F.document)
async def handle_receipt_document(message: Message, bot: Bot):
    if not message.from_user:
        return

    doc = message.document
    mime = doc.mime_type or ""

    if mime not in SUPPORTED_DOC_MIMES:
        return

    await message.answer("Processing document...")
    suffix = MIME_TO_SUFFIX.get(mime, ".bin")
    await _parse_and_save(message, bot, doc.file_id, suffix)


@router.callback_query(lambda c: c.data == "product:cancel")
async def on_product_cancel(callback: CallbackQuery):
    msg_id = callback.message.message_id
    session = _product_sessions.pop(msg_id, None)

    if not session:
        await callback.answer("Session expired.")
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    await callback.message.edit_text("Product identification cancelled.")
    await callback.answer("Cancelled.")
