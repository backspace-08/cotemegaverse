from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from core.middleware import CallbackAgeMiddleware, UserContextMiddleware

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


def setup_dispatcher() -> None:
    dp.message.middleware(UserContextMiddleware())
    dp.callback_query.middleware(UserContextMiddleware())
    dp.callback_query.middleware(CallbackAgeMiddleware())

    from features import (
        admin,
        admin_chars,
        admin_donations,
        arena,
        characters,
        donate,
        exchange,
        gacha,
        menu,
        profile,
        shop,
        top,
    )

    for module in (
        menu, gacha, characters, profile, top, exchange, donate, shop,
        admin, admin_chars, admin_donations, arena,
    ):
        dp.include_router(module.router)
