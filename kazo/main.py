import asyncio
import json
import logging
import shutil
import time
from collections import defaultdict

from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Message

from kazo.config import settings
from kazo.db.database import close_db, get_db, init_db
from kazo.handlers import (
    budget,
    categories,
    common,
    currencies,
    export,
    items,
    pending,
    receipts,
    subscriptions,
    summary,
)
from kazo.logging import setup_logging

setup_logging(level=logging.DEBUG if settings.debug else logging.INFO)
logger = logging.getLogger(__name__)

_rate_limit_windows: dict[int, list[float]] = defaultdict(list)


def check_rate_limit(chat_id: int) -> bool:
    now = time.monotonic()
    window = _rate_limit_windows[chat_id]
    cutoff = now - 3600
    _rate_limit_windows[chat_id] = [t for t in window if t > cutoff]
    return len(_rate_limit_windows[chat_id]) < settings.rate_limit_per_hour


def record_rate_limit(chat_id: int) -> None:
    _rate_limit_windows[chat_id].append(time.monotonic())


async def auth_middleware(handler, event: Message, data: dict):
    if settings.allowed_chat_ids and event.chat.id not in settings.allowed_chat_ids:
        logger.warning("Unauthorized access", extra={"chat_id": event.chat.id})
        return
    return await handler(event, data)


async def error_boundary_middleware(handler, event, data: dict):
    try:
        return await handler(event, data)
    except Exception as exc:
        from kazo.claude.client import RateLimitExceeded

        chat_id = event.chat.id if hasattr(event, "chat") and event.chat else None
        if isinstance(exc, RateLimitExceeded):
            logger.warning("Rate limit hit: %s", exc, extra={"chat_id": chat_id})
            msg = f"Rate limit reached ({settings.rate_limit_per_hour}/hour). Please wait a bit."
            try:
                if isinstance(event, Message):
                    await event.answer(msg)
                elif isinstance(event, CallbackQuery):
                    await event.answer(msg, show_alert=True)
            except Exception:
                pass
            return
        logger.error("Handler error", exc_info=True, extra={"chat_id": chat_id})
        try:
            if isinstance(event, Message):
                await event.answer("Something went wrong. Please try again.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Something went wrong.", show_alert=True)
        except Exception:
            logger.error("Failed to send error message", exc_info=True, extra={"chat_id": chat_id})


async def _health_check(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    await reader.read(4096)
    checks: dict[str, str] = {}
    try:
        db = await get_db()
        await db.execute("SELECT 1")
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = f"error: {e}"
    checks["claude_cli"] = "ok" if shutil.which("claude") else "not found"
    checks["sdk"] = "configured" if settings.anthropic_api_key else "not configured"
    healthy = checks["db"] == "ok"
    body = json.dumps({"status": "healthy" if healthy else "unhealthy", "checks": checks})
    status = "200 OK" if healthy else "503 Service Unavailable"
    response = f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n{body}"
    writer.write(response.encode())
    await writer.drain()
    writer.close()
    await writer.wait_closed()


async def main():
    await init_db()

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()

    dp.message.outer_middleware(error_boundary_middleware)
    dp.callback_query.outer_middleware(error_boundary_middleware)
    dp.message.middleware(auth_middleware)

    dp.include_router(pending.router)
    dp.include_router(receipts.router)
    dp.include_router(subscriptions.router)
    dp.include_router(summary.router)
    dp.include_router(categories.router)
    dp.include_router(currencies.router)
    dp.include_router(items.router)
    dp.include_router(budget.router)
    dp.include_router(export.router)
    dp.include_router(common.router)

    health_server = await asyncio.start_server(_health_check, "0.0.0.0", settings.health_check_port)
    logger.info("Health check listening on :%d", settings.health_check_port)

    logger.info("Starting Kazo bot")
    try:
        await dp.start_polling(bot)
    finally:
        logger.info("Shutting down gracefully...")
        health_server.close()
        await health_server.wait_closed()
        await close_db()
        logger.info("Shutdown complete")
