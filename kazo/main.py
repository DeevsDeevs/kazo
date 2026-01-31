import logging

from aiogram import Bot, Dispatcher
from aiogram.types import Message

from kazo.config import settings
from kazo.db.database import close_db, init_db
from kazo.handlers import categories, common, currencies, receipts, subscriptions, summary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def auth_middleware(handler, event: Message, data: dict):
    if settings.allowed_chat_ids and event.chat.id not in settings.allowed_chat_ids:
        logger.warning("Unauthorized access from chat_id=%d", event.chat.id)
        return
    return await handler(event, data)


async def main():
    await init_db()

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()

    dp.message.middleware(auth_middleware)

    dp.include_router(receipts.router)
    dp.include_router(subscriptions.router)
    dp.include_router(summary.router)
    dp.include_router(categories.router)
    dp.include_router(currencies.router)
    dp.include_router(common.router)

    logger.info("Starting Kazo bot")
    try:
        await dp.start_polling(bot)
    finally:
        await close_db()
