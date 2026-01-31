from kazo.categories import (
    DEFAULT_CATEGORIES,
    add_category,
    get_categories,
    remove_category,
)


async def test_defaults_returned():
    cats = await get_categories(chat_id=1)
    assert "groceries" in cats
    assert len(cats) == len(DEFAULT_CATEGORIES)


async def test_add_custom():
    added = await add_category(1, "Pets")
    assert added is True
    cats = await get_categories(1)
    assert "pets" in cats


async def test_add_duplicate_default():
    added = await add_category(1, "groceries")
    assert added is False


async def test_remove_custom():
    await add_category(1, "pets")
    removed = await remove_category(1, "pets")
    assert removed is True
    cats = await get_categories(1)
    assert "pets" not in cats


async def test_remove_default_blocked():
    removed = await remove_category(1, "groceries")
    assert removed is False
