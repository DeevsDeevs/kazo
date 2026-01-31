from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from kazo.categories import (
    DEFAULT_CATEGORIES,
    add_category,
    get_categories,
    remove_category,
)

router = Router()


@router.message(Command("categories"))
async def cmd_categories(message: Message):
    categories = await get_categories(message.chat.id)
    default_section = ", ".join(DEFAULT_CATEGORIES)
    custom = [c for c in categories if c not in DEFAULT_CATEGORIES]
    custom_section = ", ".join(custom) if custom else "none"

    await message.answer(f"Default: {default_section}\n\nCustom: {custom_section}")


@router.message(Command("addcategory"))
async def cmd_add_category(message: Message, command: CommandObject):
    if not command.args:
        await message.answer("Usage: /addcategory <name>")
        return

    name = command.args.strip().lower()
    if await add_category(message.chat.id, name):
        await message.answer(f"Category '{name}' added.")
    else:
        await message.answer(f"Category '{name}' already exists.")


@router.message(Command("removecategory"))
async def cmd_remove_category(message: Message, command: CommandObject):
    if not command.args:
        await message.answer("Usage: /removecategory <name>")
        return

    name = command.args.strip().lower()
    if await remove_category(message.chat.id, name):
        await message.answer(f"Category '{name}' removed.")
    else:
        await message.answer(f"Can't remove '{name}'. It's either a default category or doesn't exist.")
